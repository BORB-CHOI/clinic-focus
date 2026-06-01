"""kb_store.py — KB DataSource S3 업로드 + ingestion job 트리거 + KB Retrieve.

시그널별 청크 전략:
- 병원당 벡터 1개 ❌ → 시그널별 .txt 파일로 분리 (KB 파일 단위 청킹이 signal 경계 보존).
- signal_type ∈ {"self_claim", "blog", "reviews", "vision"}. 카카오 데이터는 각 signal 에 흡수.
- DESCRIPTION 은 임베딩 본문에 미포함 (상세페이지 표시용 별개).
- CLASSIFICATION 은 metadata 로만 (본문 아님).

S3 키 규약:
- 본문: {prefix}{hospital_id}/{signal_type}.txt
- 사이드카: {prefix}{hospital_id}/{signal_type}.txt.metadata.json

의료법 §56③ 준수 원칙:
- reviews 청크: _raw_to_search_result 가 SearchResult 를 metadata(hospital_id·primary_focus)
  만으로 구성하므로 청크 본문은 화면에 미표시된다(임베딩 전용). 이 구조 하에서 후기 본문
  원문(contents/body)을 청크에 포함해도 화면 노출이 발생하지 않아 §56③ 위반이 아니다.
  단, 키워드 빈도 요약은 병행 유지한다(화면 노출 가능 분리 목적 + 임베딩 풍부도 강화).
- vision 청크: 이 병원이 공개한 사진에서 식별된 장비·유형을 서술. "이 병원이 ~를 잘한다"
  형태의 평가·추천 표현 금지. 주체(이 병원이 공개한 사진에서)를 명시해야 한다.

공개 함수:
- build_self_claim_chunk(crawl_data, kakao_place) -> str
- build_blog_chunk(crawl_data, kakao_blog) -> str
- build_reviews_chunk(kakao_reviews, naver_reviews, google_reviews) -> str
- build_vision_chunk(vision_results) -> str  [신규]
- build_signal_chunks(crawl_data, kakao_place, kakao_reviews, kakao_blog, naver_reviews,
                      google_reviews, vision_results) -> dict[str, str]
- build_ingest_metadata(meta, classification) -> dict
- ingest_hospital(hospital_id, signal_chunks, metadata, *, trigger_ingestion) -> None
- retrieve_hospital(query: SearchQuery) -> list[SearchResult]
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from shared.models import (
        Classification,
        CrawlData,
        GoogleReviews,
        HospitalMeta,
        ImageAnalysisResult,
        KakaoBlog,
        KakaoPlace,
        KakaoReviews,
        NaverBlog,
        NaverPlace,
        SearchQuery,
        SearchResult,
    )

logger = logging.getLogger(__name__)


def _as_dict(obj) -> dict | None:
    """시그널 입력을 dict 로 정규화한다.

    build_*_chunk 는 dict 와 Pydantic 모델(KakaoPlace 등) 둘 다 받는다.
    - dict 면 그대로 반환
    - Pydantic 모델(model_dump 보유)이면 dict 로 변환
    - None 이면 None
    호출자가 DDB 로드 dict 든 parse 직후 모델이든 같은 코드로 흐를 수 있게 한다.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return None

# page_type 우선순위 — 정보 밀도가 높은 페이지가 청크 상위에 위치.
_PAGE_PRIORITY: dict[str, int] = {
    "service": 0,
    "about": 1,
    "main": 2,
    "doctors": 3,
    "blog": 4,
    "other": 5,
}


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

def _site_pages_text(
    crawl_data: "CrawlData | None",
    page_types: tuple[str, ...],
) -> str:
    """지정한 page_type 들의 텍스트를 priority 순으로 합쳐 반환.

    kb_ingest._site_excerpts 와 동일한 정렬 로직.
    """
    if crawl_data is None or not crawl_data.pages:
        return ""
    pages = [p for p in crawl_data.pages if p.page_type in page_types]
    pages.sort(key=lambda p: _PAGE_PRIORITY.get(p.page_type, 9))
    blocks: list[str] = []
    for p in pages:
        text = (p.html_text or "").strip()
        if text:
            blocks.append(f"[{p.page_type}] {p.url}\n{text}")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# A. 청크 빌더 (순수 함수, 네트워크 없음)
# ---------------------------------------------------------------------------

def build_self_claim_chunk(
    crawl_data: "CrawlData | None" = None,
    kakao_place: "KakaoPlace | dict | None" = None,
) -> str:
    """자칭 시그널 청크.

    자체 사이트 service/about/main 텍스트 + 카카오 tags(자칭 키워드) +
    mystore_intro + hira.specialized_field + hira.medical_center_type 합산.

    Args:
        crawl_data: BE 크롤링 결과. None 이면 사이트 텍스트 생략.
        kakao_place: kakao_place_adapter.parse_place() 출력. None 이면 카카오 부분 생략.

    Returns:
        자연어 청크 문자열. 데이터 없으면 "".
    """
    parts: list[str] = []
    kakao_place = _as_dict(kakao_place)

    # 1. 자체 사이트 service/about/main 페이지 (정보 밀도 높은 순)
    site_text = _site_pages_text(crawl_data, ("service", "about", "main"))
    if site_text:
        parts.append(f"[자체 사이트 자칭 정보]\n{site_text}")

    # 2. 카카오 자칭 키워드
    if kakao_place:
        tags: list[str] = kakao_place.get("tags") or []
        mystore_intro: str | None = kakao_place.get("mystore_intro")
        hira: dict = kakao_place.get("hira") or {}
        specialized_field: str | None = hira.get("specialized_field")
        medical_center_type: str | None = hira.get("medical_center_type")

        kakao_parts: list[str] = []
        if tags:
            kakao_parts.append(f"카카오 자칭 키워드: {', '.join(tags)}")
        if mystore_intro:
            kakao_parts.append(f"병원 소개: {mystore_intro}")
        if medical_center_type:
            kakao_parts.append(f"의료기관 종류: {medical_center_type}")
        if specialized_field:
            kakao_parts.append(f"HIRA 전문 분야: {specialized_field}")

        if kakao_parts:
            parts.append("[카카오 자칭 정보]\n" + "\n".join(kakao_parts))

    return "\n\n".join(parts)


def build_blog_chunk(
    crawl_data: "CrawlData | None" = None,
    kakao_blog: "KakaoBlog | dict | None" = None,
    naver_blog: "NaverBlog | dict | None" = None,
) -> str:
    """블로그 시그널 청크.

    자체 사이트 blog 페이지 + 카카오 blog seeds + 네이버 블로그 posts 의
    title + 본문(contents/description) 합산. 작성자 PII 는 parse 단계에서 이미 제거됨.

    Args:
        crawl_data: BE 크롤링 결과. None 이면 사이트 블로그 텍스트 생략.
        kakao_blog: parse_blog() 출력(KakaoBlog 또는 dict). None 이면 생략.
        naver_blog: parse_naver_blog() 출력(NaverBlog 또는 dict). None 이면 생략.

    Returns:
        자연어 청크 문자열. 데이터 없으면 "".
    """
    parts: list[str] = []
    kakao_blog = _as_dict(kakao_blog)
    naver_blog = _as_dict(naver_blog)

    # 1. 자체 사이트 blog 페이지
    site_blog_text = _site_pages_text(crawl_data, ("blog",))
    if site_blog_text:
        parts.append(f"[자체 사이트 블로그]\n{site_blog_text}")

    # 2. 카카오 블로그 seeds
    if kakao_blog:
        seeds: list[dict] = kakao_blog.get("seeds") or []
        seed_blocks: list[str] = []
        for seed in seeds:
            title = (seed.get("title") or "").strip()
            contents = (seed.get("contents") or "").strip()
            if title or contents:
                block = f"제목: {title}" if title else ""
                if contents:
                    block = f"{block}\n내용: {contents}" if block else f"내용: {contents}"
                seed_blocks.append(block)
        if seed_blocks:
            total_posts = kakao_blog.get("total_posts")
            header = "카카오 블로그 포스트"
            if total_posts:
                header += f" (전체 {total_posts}건 중 상위)"
            parts.append(f"[{header}]\n" + "\n---\n".join(seed_blocks))

    # 3. 네이버 블로그 posts (title + description 발췌)
    if naver_blog:
        posts: list[dict] = naver_blog.get("posts") or []
        post_blocks: list[str] = []
        for post in posts:
            title = (post.get("title") or "").strip()
            desc = (post.get("description") or "").strip()
            if title or desc:
                block = f"제목: {title}" if title else ""
                if desc:
                    block = f"{block}\n내용: {desc}" if block else f"내용: {desc}"
                post_blocks.append(block)
        if post_blocks:
            total = naver_blog.get("total")
            header = "네이버 블로그 포스트"
            if total:
                header += f" (전체 {total}건 중 상위)"
            parts.append(f"[{header}]\n" + "\n---\n".join(post_blocks))

    return "\n\n".join(parts)


def build_reviews_chunk(
    kakao_reviews: "KakaoReviews | dict | None" = None,
    naver_reviews: "NaverPlace | dict | None" = None,
    google_reviews: "GoogleReviews | dict | None" = None,
) -> str:
    """후기 시그널 청크 — 키워드 빈도 요약 + 후기 본문 원문(임베딩 전용).

    [의료법 §56③ 판단]
    _raw_to_search_result 가 SearchResult 를 metadata(hospital_id·primary_focus)만으로
    구성하므로, 이 청크 본문은 화면에 미표시되는 임베딩 전용 텍스트다. 따라서 후기
    본문 원문을 청크에 포함해도 §56③ 위반이 발생하지 않는다.

    [중요] 이 면제는 조건부다. 다음 중 하나라도 변경되면 즉시 §56③ 위반이 된다:
    - _raw_to_search_result 반환값에 청크 본문(content/text)을 추가
    - retrieve_hospital 또는 BE API 가 청크 원문을 사용자 화면에 노출
    - KB Retrieve 외 다른 경로의 벡터 검색이 청크 텍스트를 반환
    위 변경 시 반드시 medical-language-reviewer 에 재검수 의뢰할 것.

    구성:
    1. 키워드 빈도 요약 — 화면 노출 가능 형태, 임베딩 풍부도 보강.
       "방문자 후기 강점 키워드 — 전문성 145회, 친절 164회, ..." 형태.
    2. 후기 본문 원문 — 임베딩 어휘 풍부도 강화. 화면 미표시.
       - 카카오: parse_reviews() 출력 reviews[i]["contents"]
         (parse 단계 _mask_review_item 에서 owner PII 이미 제거됨)
       - 네이버: parse_place() 출력 reviews[i]["body"]
         (parse 단계에서 author PII 이미 제거됨)
       - 구글: parse_google_reviews() 출력 reviews[i]["text"]
         (parse 단계에서 authorAttribution PII 이미 제거됨)

    Args:
        kakao_reviews: parse_reviews() 출력 (KakaoReviews 모델 또는 dict). None 이면 생략.
        naver_reviews: NaverPlace 형태 (keyword_stats + reviews 키). 모델 또는 dict.
        google_reviews: parse_google_reviews() 출력 (GoogleReviews 또는 dict). None 이면 생략.

    Returns:
        키워드 빈도 요약 + 후기 본문 원문 결합 문자열. 데이터 없으면 "".
    """
    parts: list[str] = []
    kakao_reviews = _as_dict(kakao_reviews)
    naver_reviews = _as_dict(naver_reviews)
    google_reviews = _as_dict(google_reviews)

    # ---- 1. 카카오 ----
    if kakao_reviews:
        # 1a. 키워드 빈도 요약
        kf: dict[str, int] = kakao_reviews.get("keyword_frequency") or {}
        if kf:
            kf_text = ", ".join(f"{k} {v}회" for k, v in sorted(kf.items(), key=lambda x: -x[1]))
            total = kakao_reviews.get("total_reviews")
            avg = kakao_reviews.get("average_score")
            header_parts = ["카카오 방문자 후기 강점 키워드"]
            if total:
                header_parts.append(f"(총 {total}건")
                if avg:
                    header_parts.append(f"/ 평균 {avg}점)")
                else:
                    header_parts[-1] += ")"
            parts.append(" ".join(header_parts) + f" — {kf_text}")

        # 1b. 후기 본문 원문 (임베딩 전용 — 화면 미표시)
        kakao_review_items: list[dict] = kakao_reviews.get("reviews") or []
        kakao_bodies = [
            (r.get("contents") or "").strip()
            for r in kakao_review_items
            if (r.get("contents") or "").strip()
        ]
        if kakao_bodies:
            parts.append(
                "[카카오 방문자 후기 본문 — 임베딩 전용]\n"
                + "\n---\n".join(kakao_bodies)
            )

    # ---- 2. 네이버 ----
    if naver_reviews:
        # 2a. keyword_stats 빈도 요약
        ks: dict[str, int] = naver_reviews.get("keyword_stats") or {}
        if ks:
            ks_text = ", ".join(f"{k} {v}회" for k, v in sorted(ks.items(), key=lambda x: -x[1]))
            visitor_count = naver_reviews.get("visitor_count")
            header = "네이버 방문자 키워드"
            if visitor_count:
                header += f" (누적 방문 {visitor_count}명)"
            parts.append(f"{header} — {ks_text}")

        # 2b. 후기 본문 원문 (임베딩 전용 — 화면 미표시)
        # naver_place_adapter.parse_place() 출력: reviews[i]["body"]
        naver_review_items: list[dict] = naver_reviews.get("reviews") or []
        naver_bodies = [
            (r.get("body") or "").strip()
            for r in naver_review_items
            if (r.get("body") or "").strip()
        ]
        if naver_bodies:
            parts.append(
                "[네이버 방문자 후기 본문 — 임베딩 전용]\n"
                + "\n---\n".join(naver_bodies)
            )

    # ---- 3. 구글 ----
    if google_reviews:
        # 3a. keyword_frequency 빈도 요약
        gf: dict[str, int] = google_reviews.get("keyword_frequency") or {}
        if gf:
            gf_text = ", ".join(f"{k} {v}회" for k, v in sorted(gf.items(), key=lambda x: -x[1]))
            total = google_reviews.get("user_ratings_total")
            rating = google_reviews.get("rating")
            header = "구글 리뷰 키워드"
            if total:
                header += f" (총 {total}건"
                header += f" / 평균 {rating}점)" if rating else ")"
            parts.append(f"{header} — {gf_text}")

        # 3b. 후기 본문 원문 (임베딩 전용 — 화면 미표시)
        # google_places_adapter.parse_google_reviews() 출력: reviews[i]["text"]
        google_review_items: list[dict] = google_reviews.get("reviews") or []
        google_bodies = [
            (r.get("text") or "").strip()
            for r in google_review_items
            if (r.get("text") or "").strip()
        ]
        if google_bodies:
            parts.append(
                "[구글 리뷰 본문 — 임베딩 전용]\n"
                + "\n---\n".join(google_bodies)
            )

    return "\n\n".join(parts)


def build_vision_chunk(
    vision_results: "list[ImageAnalysisResult] | list[dict] | None" = None,
) -> str:
    """Vision 시그널 청크 — 식별된 장비 집계 + 이미지 유형 분포.

    [의료법 주체 명시 원칙]
    "이 병원이 자기 사이트에서 ~를 잘한다" 형태의 평가·추천 표현은 금지된다.
    허용: "이 병원이 공개한 사진에서 식별된 장비/유형"처럼 출처(병원 공개 사진)를
    주체로 명시하는 서술. Vision 분류 결과는 사진에서 관찰된 사실을 기록할 뿐이며,
    이 병원이 해당 시술/장비를 보유·제공한다는 광고성 평가가 아니다.

    청크 본문은 _raw_to_search_result 가 metadata 만 반환하므로 화면 미표시.
    임베딩 어휘 강화가 목적.

    Args:
        vision_results: analyze_images() 반환값 (ImageAnalysisResult 리스트 또는 dict 리스트).
                        None 또는 빈 리스트면 "" 반환.

    Returns:
        Vision 청크 문자열. 데이터 없으면 "".
    """
    if not vision_results:
        return ""

    # dict 또는 Pydantic 모델 둘 다 수용
    results_as_dicts: list[dict] = []
    for r in vision_results:
        if isinstance(r, dict):
            results_as_dicts.append(r)
        else:
            dump = getattr(r, "model_dump", None)
            if callable(dump):
                results_as_dicts.append(dump())

    if not results_as_dicts:
        return ""

    total = len(results_as_dicts)

    # detected_devices 집계 — 등장 횟수 카운트
    device_counts: dict[str, int] = {}
    for r in results_as_dicts:
        for d in (r.get("detected_devices") or []):
            d = (d or "").strip()
            if d:
                device_counts[d] = device_counts.get(d, 0) + 1

    # image_category 분포
    category_counts: dict[str, int] = {}
    for r in results_as_dicts:
        cat = (r.get("image_category") or "기타").strip()
        category_counts[cat] = category_counts.get(cat, 0) + 1

    parts: list[str] = [
        f"[Vision 분석 — 이 병원이 공개한 사진 {total}장 분석 결과]"
    ]

    # 장비 목록 (등장 횟수 내림차순)
    if device_counts:
        device_list = ", ".join(
            f"{d}({cnt}장)" if cnt > 1 else d
            for d, cnt in sorted(device_counts.items(), key=lambda x: -x[1])
        )
        parts.append(f"이 병원이 공개한 사진에서 식별된 장비·시술 관련 장면: {device_list}")
    else:
        parts.append("이 병원이 공개한 사진에서 특정 의료기기·시술 장비는 식별되지 않음")

    # 이미지 유형 분포
    cat_desc_parts = []
    for cat, cnt in sorted(category_counts.items(), key=lambda x: -x[1]):
        pct = round(cnt / total * 100)
        cat_desc_parts.append(f"{cat} {pct}%({cnt}장)")
    parts.append(f"사진 유형 분포: {', '.join(cat_desc_parts)}")

    return "\n".join(parts)


# 한 청크에 부착할 동의어 최대 개수 — 임베딩 본문 비대 방지.
_MAX_SYNONYM_ADDITIONS = 60

# 동의어 클러스터 캐시 (dictionaries 에서 1회 로드).
_SYNONYM_CLUSTERS: list[list[str]] | None = None


def _enrich_with_synonyms(text: str) -> str:
    """문서(병원 청크)에 동의어 클러스터를 부착해 임베딩 어휘를 **양방향** 확장한다.

    문제: 병원 본문에 "심상성 우췌"로만 적혀 있으면 사용자가 "사마귀"로 검색해도
    Titan v2 의 한국어 의학 동의어 갭(cos 0.25) 때문에 못 찾는다(쿼리 확장만으로는
    쿼리에 트리거 단어가 정확히 있어야 작동 — 취약).

    해결(설계 문서 트랙 A): 청크에 클러스터 멤버가 하나라도 있으면 나머지 멤버를
    `[관련 의학 용어]` 줄로 덧붙인다. 그러면 본문이 어느 표현을 쓰든 임베딩이 일반어·
    학명·영문·치료를 모두 담아 어느 방향 쿼리에도 매칭된다. 임베딩 전용(화면 미표시)
    이라 §56 무관.

    오매칭 방지: 길이 2 미만 멤버(점·목·침·냉)는 **트리거로 쓰지 않는다** — "시점"의
    "점" 같은 부분문자열 사고 차단. 단 트리거된 클러스터의 짧은 멤버는 부착 대상에는
    포함(임베딩 어휘 보강).
    """
    global _SYNONYM_CLUSTERS
    if not text:
        return text
    if _SYNONYM_CLUSTERS is None:
        from ai.search.dictionaries import build_synonym_clusters  # 순환·boto3 무관
        _SYNONYM_CLUSTERS = build_synonym_clusters()

    additions: list[str] = []
    seen: set[str] = set()
    for cluster in _SYNONYM_CLUSTERS:
        # 트리거: len>=2 멤버가 본문에 등장해야 클러스터 활성 (짧은 키 오매칭 방지)
        if not any(len(m) >= 2 and m in text for m in cluster):
            continue
        for m in cluster:
            if m not in text and m not in seen:
                seen.add(m)
                additions.append(m)
                if len(additions) >= _MAX_SYNONYM_ADDITIONS:
                    break
        if len(additions) >= _MAX_SYNONYM_ADDITIONS:
            break

    if not additions:
        return text
    return f"{text}\n[관련 의학 용어] {', '.join(additions)}"


# ── 의료광고(§56) 표현 스크럽 — 임베딩 입력에서만 중화 ──────────────────
# 청크는 화면 미표시(임베딩 전용)이라 §56 직접 위반은 아니나, 광고·과장 어휘가 임베딩에 섞이면
# (1) 자칭 광고가 검색 노출 근거가 되고 (2) 후기·블로그의 과장·체험단성 어휘가 시그널을 부풀린다.
# 실측(강남 2133 자체사이트 + 후기/블로그) 기반 **명백 위반만**. "전문"(전문의·전문병원 = 합법 사실)
# 등 회색·합법어는 제외. "완치/안전한/무통/부작용없"은 환자 후기에선 경험 서술일 수 있어 LIGHT 에서 제외.

# STRONG (자칭 self_claim — 병원이 직접 쓴 광고라 적법성 차원에서 강하게)
_AD_SCRUB_STRONG = [
    r"\d+\s*년\s*무\s*사고", r"무\s*사고",
    r"안전(하게|한|하고|성)?(?=\s*(진료|치료|시술|수술|관리|마취|분만|출산|성형))",
    r"무\s*통(?![가-힣])", r"통증\s*(이)?\s*없[는이어요]*",
    r"완\s*치", r"부작용\s*(이)?\s*(없|제로|최소화?)[는이어요]*",
    r"(확실한|탁월한|뛰어난|놀라운)\s*효과", r"효과\s*(만점|짱|굿)",
    # 효능·결과 보장 (§56 — medical-language-reviewer 권고)
    r"(효과|성공|결과|완치|치료|완벽)\s*(보장|보증)", r"\d+\s*(건|례)\s*성공",
    r"독보적[인]?", r"명\s*품", r"프리미엄", r"premium",
    r"최상의?", r"유일(한|무이한)?", r"국내\s*유일",
    # 우월·최신성 과장 (§56 — reviewer 권고: 최첨단·최신·유명·완벽)
    r"최\s*첨단", r"최\s*신\s*(기술|장비|시설|의료기기|시스템|치료법|기기)",
    r"유\s*명(한|하다|하고)?", r"완\s*벽(하게|한|히)?",
    r"강력?\s*추천", r"강\s*추", r"인생\s*(병원|시술|템플?)",
    r"국내\s*최고", r"최고의?", r"넘버\s*원", r"\bno\.?\s*1\b",
    r"명\s*의(?![료원])", r"베스트", r"\bbest\b", r"\d+\s*위\b",
]
# LIGHT (후기·블로그 — 저자가 환자/제3자라 §56 직접 적용 X. 순수 과장·우월 광고어만, 경험 서술 보존)
_AD_SCRUB_LIGHT = [
    r"강력?\s*추천", r"강\s*추", r"효과\s*(만점|짱|굿)", r"인생\s*(병원|시술|템플?)",
    r"국내\s*최고", r"최고의?", r"넘버\s*원", r"\bno\.?\s*1\b",
    r"명\s*의(?![료원])", r"베스트", r"\bbest\b", r"독보적[인]?", r"명\s*품", r"프리미엄",
    # 우월·최신성 과장 (reviewer 권고) — 환자 경험 서술(완치/안전/무통/부작용없)은 보존
    r"최\s*첨단", r"최\s*신\s*(기술|장비|시설|의료기기|시스템|치료법|기기)",
    r"유\s*명(한|하다|하고)?", r"완\s*벽(하게|한|히)?",
]
_AD_SCRUB_STRONG_RE = re.compile("|".join(_AD_SCRUB_STRONG), re.IGNORECASE)
_AD_SCRUB_LIGHT_RE = re.compile("|".join(_AD_SCRUB_LIGHT), re.IGNORECASE)


def _scrub_ad_phrases(text: str, *, aggressive: bool) -> str:
    """청크 텍스트에서 의료광고·과장 표현을 중화(임베딩 입력 전용).

    aggressive=True(자칭): STRONG 목록. False(후기·블로그): LIGHT 목록(순수 광고어만).
    매칭 토큰만 공백 치환 — 의료 명사("안전한 수술"→"수술")는 보존. focus 라벨·화면엔 무관.
    """
    if not text:
        return text
    rx = _AD_SCRUB_STRONG_RE if aggressive else _AD_SCRUB_LIGHT_RE
    cleaned = rx.sub(" ", text)
    return re.sub(r"[ \t]{2,}", " ", cleaned)


def build_signal_chunks(
    crawl_data: "CrawlData | None" = None,
    kakao_place: "KakaoPlace | dict | None" = None,
    kakao_reviews: "KakaoReviews | dict | None" = None,
    kakao_blog: "KakaoBlog | dict | None" = None,
    naver_reviews: "NaverPlace | dict | None" = None,
    naver_blog: "NaverBlog | dict | None" = None,
    google_reviews: "GoogleReviews | dict | None" = None,
    vision_results: "list | None" = None,
) -> dict[str, str]:
    """모든 시그널 청크를 조립하여 비어있지 않은 것만 반환.

    각 인자는 dict 또는 대응 Pydantic 모델(KakaoPlace 등) 둘 다 받는다.
    자칭·블로그 청크는 ``_enrich_with_synonyms`` 로 **문서-측 동의어 주입**해 임베딩
    어휘를 양방향 확장한다.
    reviews 청크는 키워드 빈도 + 후기 본문 원문을 포함한다. 청크 본문은
    화면에 미표시(임베딩 전용)이므로 _enrich_with_synonyms 는 생략하지 않는다.
    vision 청크는 analyze_images() 결과가 있을 때만 추가된다(시연 10개 한정).

    Args:
        vision_results: analyze_images() 결과 (ImageAnalysisResult 리스트 또는 dict 리스트).
                        None 또는 빈 리스트면 vision 청크 미생성.

    Returns:
        {signal_type: text} — signal_type ∈ {"self_claim", "blog", "reviews", "vision"}.
        빈 텍스트 시그널은 제외.
    """
    result: dict[str, str] = {}

    # 광고·과장 표현만 스크럽(임베딩 전용). **doc-side 동의어 주입(_enrich_with_synonyms)은
    # 제거** — 트리거 단어 1회(예: 19000자 치과 사이트의 "탈모" 1회)만 있어도 동의어 클러스터
    # 전체를 청크에 박아, 쿼리(같은 클러스터로 확장)와 "덩어리끼리" 매칭되며 임베딩 변별력을
    # 파괴했다(치과가 "M자 탈모" 검색 0.708 1위·진짜 모발병원은 후순위 — 2026-05-31 실측).
    # 한국어 의학 동의어 갭은 **쿼리-side 확장(process_query)** 으로만 메운다(쿼리만 확장,
    # 문서는 진짜 내용 그대로 임베딩 → 변별력 보존).
    sc = build_self_claim_chunk(crawl_data=crawl_data, kakao_place=kakao_place)
    if sc:
        result["self_claim"] = _scrub_ad_phrases(sc, aggressive=True)

    bc = build_blog_chunk(crawl_data=crawl_data, kakao_blog=kakao_blog, naver_blog=naver_blog)
    if bc:
        result["blog"] = _scrub_ad_phrases(bc, aggressive=False)

    rc = build_reviews_chunk(
        kakao_reviews=kakao_reviews,
        naver_reviews=naver_reviews,
        google_reviews=google_reviews,
    )
    if rc:
        result["reviews"] = _scrub_ad_phrases(rc, aggressive=False)

    vc = build_vision_chunk(vision_results=vision_results)
    if vc:
        result["vision"] = vc

    return result


# ---------------------------------------------------------------------------
# B. metadata 빌더
# ---------------------------------------------------------------------------

def build_ingest_metadata(
    meta: "HospitalMeta",
    classification: "Classification",
) -> dict:
    """KB Retrieve filter 용 metadataAttributes dict (평탄).

    kb_ingest._build_metadata 와 동일 규약:
    - team_id="clinic-focus" 필수 (KB 02팀 공유, 격리 필터용)
    - 빈 primary_focus → 키 제외 (빈 리스트 KB 거절 실측 함정)
    - lat/lng None → 키 제외 (null 값 KB 거절 실측 함정)

    Args:
        meta: HospitalMeta 인스턴스.
        classification: Classification 인스턴스.

    Returns:
        metadataAttributes 안쪽 평탄 dict. {"metadataAttributes": ...} 래핑은 포함하지 않음.
    """
    md: dict = {
        "team_id": "clinic-focus",
        "hospital_id": meta.hospital_id,
        "name": meta.name,
        "standard_specialty": classification.standard_specialty,
        "sido": meta.location.sido,
        "sigungu": meta.location.sigungu,
        "confidence_score": classification.confidence.score,
    }
    # 빈 리스트는 KB 가 invalid metadata 로 거절 (2026-05-26 실측 확인). 키 자체 제외.
    if classification.primary_focus:
        md["primary_focus"] = classification.primary_focus
    # None 값도 KB 거절 실측 함정 동일. 좌표 없는 병원은 위치 검색에서 자동 제외.
    if meta.location.lat is not None:
        md["lat"] = meta.location.lat
    if meta.location.lng is not None:
        md["lng"] = meta.location.lng
    return md


# ---------------------------------------------------------------------------
# C. ingest
# ---------------------------------------------------------------------------

def ingest_hospital(
    hospital_id: str,
    signal_chunks: dict[str, str],
    metadata: dict,
    *,
    trigger_ingestion: bool = False,
) -> None:
    """시그널 청크를 KB DataSource S3 에 업로드하고 선택적으로 ingestion job 트리거.

    S3 키 규약:
      본문:   {prefix}{hospital_id}/{signal_type}.txt
      사이드카: {prefix}{hospital_id}/{signal_type}.txt.metadata.json
    사이드카 포맷: {"metadataAttributes": {**metadata, "signal_type": signal_type}}

    Args:
        hospital_id: 병원 고유 ID.
        signal_chunks: build_signal_chunks() 반환 dict. 비어있지 않은 시그널만 담겨야 함.
        metadata: build_ingest_metadata() 반환 평탄 dict (metadataAttributes 안쪽).
        trigger_ingestion: True 면 업로드 완료 후 StartIngestionJob 1회 호출.
                           배치 시 False 로 다 올린 뒤 마지막 병원에서만 True 사용.

    Raises:
        KBIngestError: S3 업로드 또는 ingestion job 트리거 실패 시.
    """
    from ai.core.exceptions import KBIngestError  # 순환 import 방지

    bucket = os.environ.get("KB_DATASOURCE_S3_BUCKET")
    prefix = (os.environ.get("KB_DATASOURCE_S3_PREFIX") or "").lstrip("/")
    kb_id = os.environ.get("KB_ID")
    ds_id = os.environ.get("KB_DATA_SOURCE_ID")
    region = os.environ.get("AWS_REGION", "us-east-1")

    if not bucket:
        raise KBIngestError("환경변수 KB_DATASOURCE_S3_BUCKET 이 설정되지 않았습니다.")

    s3_client = boto3.client("s3", region_name=region)
    agent_client = boto3.client("bedrock-agent", region_name=region)

    for signal_type, text in signal_chunks.items():
        if not text:
            # build_signal_chunks 에서 이미 제외되어야 하지만 방어적으로 재확인
            logger.debug("ingest_hospital: 빈 텍스트 시그널 스킵 (%s)", signal_type)
            continue

        text_key = f"{prefix}{hospital_id}/{signal_type}.txt"
        meta_key = f"{text_key}.metadata.json"

        # 사이드카: metadataAttributes 에 signal_type 추가 (retrieve 시 시그널 종류 필터 가능)
        sidecar = {"metadataAttributes": {**metadata, "signal_type": signal_type}}

        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=text_key,
                Body=text.encode("utf-8"),
                ContentType="text/plain; charset=utf-8",
            )
            s3_client.put_object(
                Bucket=bucket,
                Key=meta_key,
                Body=json.dumps(sidecar, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as exc:
            logger.error(
                "KB S3 업로드 실패 (hospital_id=%s, signal=%s): %s",
                hospital_id, signal_type, exc,
            )
            raise KBIngestError(
                f"S3 업로드 실패 (hospital_id={hospital_id}, signal={signal_type}): {exc}"
            ) from exc

        logger.info(
            "KB S3 업로드 완료: hospital_id=%s signal=%s key=%s",
            hospital_id, signal_type, text_key,
        )

    if not trigger_ingestion:
        return

    if not kb_id or not ds_id:
        raise KBIngestError(
            "trigger_ingestion=True 이지만 KB_ID 또는 KB_DATA_SOURCE_ID 환경변수 미설정"
        )

    try:
        job = agent_client.start_ingestion_job(
            knowledgeBaseId=kb_id,
            dataSourceId=ds_id,
        )
        job_id = job["ingestionJob"]["ingestionJobId"]
        status = job["ingestionJob"]["status"]
        logger.info("KB ingestion job 시작: job_id=%s status=%s", job_id, status)
    except Exception as exc:
        logger.error("StartIngestionJob 실패 (hospital_id=%s): %s", hospital_id, exc)
        raise KBIngestError(
            f"StartIngestionJob 실패 (hospital_id={hospital_id}): {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# D. retrieve_hospital — KB Retrieve 래퍼
# ---------------------------------------------------------------------------

# bounding box 근사: 위도 1° ≈ 111 km → 1 km ≈ 0.009°
# 경도는 위도에 따라 달라지지만 한국 중위도(37°) 기준 보수적으로 동일 적용.
_DEG_PER_KM = 0.009

# KB Retrieve API 한 번 호출에 반환되는 최대 청크 수.
_KB_MAX_RESULTS = 100


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 공식으로 두 지점 간 거리(km)를 계산한다."""
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_kb_filter(
    sido: str | None = None,
    sigungu: str | None = None,
    specialty: "str | list[str] | None" = None,
    min_confidence: int | None = None,
    lat_range: tuple[float, float] | None = None,
    lng_range: tuple[float, float] | None = None,
) -> dict:
    """KB Retrieve vectorSearchConfiguration.filter 를 조립한다.

    team_id="clinic-focus" 는 항상 포함 (KB 공유 격리 필수).
    나머지 조건이 있으면 andAll 로 묶는다.

    KB 필터 DSL:
      {"equals": {"key": ..., "value": ...}}
      {"greaterThanOrEquals": {"key": ..., "value": ...}}
      {"andAll": [...]}
    """
    conditions: list[dict] = [
        {"equals": {"key": "team_id", "value": "clinic-focus"}}
    ]

    if sido:
        conditions.append({"equals": {"key": "sido", "value": sido}})
    if sigungu:
        conditions.append({"equals": {"key": "sigungu", "value": sigungu}})
    if specialty:
        # specialty 가 리스트면 그 중 하나라도 일치(in) — 추론 specialty 에 '기타'를 함께
        # 허용해 분류 못 한 특화 부티크를 하드 배제하지 않으려는 용도. 단일 문자열이면 equals.
        if isinstance(specialty, (list, tuple, set)):
            vals = [s for s in specialty if s]
            if len(vals) == 1:
                conditions.append({"equals": {"key": "standard_specialty", "value": vals[0]}})
            elif vals:
                conditions.append({"in": {"key": "standard_specialty", "value": vals}})
        else:
            conditions.append({"equals": {"key": "standard_specialty", "value": specialty}})
    if min_confidence:
        # min_confidence=0(또는 None)이면 신뢰도 하드필터 없음 — 모든 병원 노출.
        # 의료법: 특정 병원만 보이고 일부가 검색에서 사라지면 차별 노출 소지가 있어,
        # 신뢰도는 '거르는' 기준이 아니라 '정렬/표시'용으로만 쓴다(랭킹은 relevance 우선).
        conditions.append(
            {"greaterThanOrEquals": {"key": "confidence_score", "value": min_confidence}}
        )
    if lat_range is not None:
        lat_min, lat_max = lat_range
        conditions.append({"greaterThanOrEquals": {"key": "lat", "value": lat_min}})
        conditions.append({"lessThanOrEquals": {"key": "lat", "value": lat_max}})
    if lng_range is not None:
        lng_min, lng_max = lng_range
        conditions.append({"greaterThanOrEquals": {"key": "lng", "value": lng_min}})
        conditions.append({"lessThanOrEquals": {"key": "lng", "value": lng_max}})

    if len(conditions) == 1:
        # team_id 하나뿐이면 단일 조건으로 반환
        return conditions[0]
    return {"andAll": conditions}


def _kb_retrieve(
    client,
    kb_id: str,
    query_text: str,
    kb_filter: dict,
    n_results: int,
) -> list[dict]:
    """bedrock-agent-runtime:Retrieve 를 호출하고 retrievalResults 리스트를 반환한다.

    Raises:
        KBRetrieveError: API 호출 실패 시.
    """
    from ai.core.exceptions import KBRetrieveError  # 순환 import 방지

    try:
        resp = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query_text},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": min(n_results, _KB_MAX_RESULTS),
                    "filter": kb_filter,
                }
            },
        )
    except Exception as exc:
        logger.error("KB Retrieve 실패: %s", exc)
        raise KBRetrieveError(f"KB Retrieve 실패: {exc}") from exc

    return resp.get("retrievalResults", [])


def _dedup_by_hospital(raw_results: list[dict]) -> dict[str, dict]:
    """같은 hospital_id 의 청크 중 최고 score 1개만 남긴다.

    반환값: {hospital_id: raw_result_item}
    """
    by_hospital: dict[str, dict] = {}
    for r in raw_results:
        md = r.get("metadata") or {}
        hid = md.get("hospital_id")
        if not hid:
            continue
        score = float(r.get("score") or 0.0)
        if hid not in by_hospital or score > float(by_hospital[hid].get("score") or 0.0):
            by_hospital[hid] = r
    return by_hospital


def _build_interpretation(processed) -> str | None:
    """ProcessedQuery 로부터 사용자 표시용 "이렇게 이해했어요" 문자열을 만든다.

    예: "사마귀 어디가 좋을까" → "사마귀 · 진료과: 피부과".
    FE 가 검색 결과 상단에 노출하면 사용자가 오해석을 즉시 인지하고 재검색 가능.
    의료 키워드를 하나도 못 뽑았으면 None (해석 표시 안 함).
    """
    if not processed.medical_terms:
        return None
    parts: list[str] = [", ".join(processed.medical_terms)]
    if processed.inferred_specialty:
        parts.append(f"진료과: {processed.inferred_specialty}")
    if processed.inferred_focus:
        parts.append(f"분야: {' / '.join(processed.inferred_focus)}")
    return " · ".join(parts)


def _raw_to_search_result(
    item: dict,
    similarity_score: float | None = None,
    distance_km: float | None = None,
    query_interpretation: str | None = None,
) -> "SearchResult":
    """KB Retrieve raw result 항목을 SearchResult 로 변환한다.

    [의료법 §56③ — 절대 어기지 말 것]
    청크 본문(item["content"]["text"])을 SearchResult 에 포함하면 안 된다.
    reviews/vision 청크는 후기 본문·사진 분석을 임베딩 전용으로만 담고 있어
    화면 미표시를 전제로 §56③ 면제를 받는다. 본문을 결과로 노출하는 순간
    환자 후기 광고 노출이 되어 위반이다. metadata 필드만 사용할 것.
    """
    from shared.models import SearchResult  # 순환 import 방지

    md = item.get("metadata") or {}
    hospital_id: str = md.get("hospital_id") or ""

    # primary_focus — list[str] 또는 문자열(JSON) 방어 처리
    raw_focus = md.get("primary_focus") or []
    if isinstance(raw_focus, str):
        try:
            raw_focus = json.loads(raw_focus)
        except (json.JSONDecodeError, TypeError):
            raw_focus = []
    matched_focus: list[str] = raw_focus if isinstance(raw_focus, list) else []

    return SearchResult(
        hospital_id=hospital_id,
        similarity_score=similarity_score,
        distance_km=distance_km,
        matched_focus=matched_focus,
        query_interpretation=query_interpretation,
    )


def retrieve_hospital(query: "SearchQuery") -> "list[SearchResult]":
    """자연어 쿼리로 KB Retrieve 를 호출해 유사 병원 목록을 반환한다.

    동작:
    - query.query_text 필수 (KB Retrieve 는 빈 쿼리 불가).
    - query.lat + query.lng 가 있으면 bounding box 필터 추가 + haversine 재필터링.
    - 결과 청크를 hospital_id 기준으로 dedup(최고 score 1개) 후 SearchResult 변환.
    - 빈 결과 시 sido/sigungu/specialty/min_confidence 필터를 완화하여 fallback 재시도.
    - team_id="clinic-focus" 필터는 항상 포함 (KB 공유 격리).

    Args:
        query: SearchQuery 인스턴스. query_text 필수.

    Returns:
        SearchResult 리스트 (최대 query.limit 개).

    Raises:
        InvalidQueryError: query_text 가 비었을 때.
        KBRetrieveError: KB Retrieve API 호출 실패 시.
    """
    from ai.core.exceptions import InvalidQueryError, KBRetrieveError  # 순환 import 방지
    from ai.search.query_processor import process_query

    q_text = (query.query_text or "").strip()
    if not q_text:
        raise InvalidQueryError("retrieve_hospital: query_text 가 비어있습니다. KB Retrieve 는 빈 쿼리 불가.")

    # 검색어 전처리 — 불용어 제거 + 의료 동의어 확장 + 진료과 추론.
    # embedding_text(동의어 확장본)로 임베딩 매칭률을 높이고, 추론 진료과는
    # 사용자가 specialty 를 명시 안 했을 때만 메타필터로 보강(명시값 우선).
    processed = process_query(q_text)
    retrieve_text = processed.embedding_text or q_text
    interpretation = _build_interpretation(processed)  # FE "이렇게 이해했어요" 박스용

    # specialty 메타필터 값 결정.
    # - 사용자가 명시 선택한 specialty(query.specialty)는 의도가 분명하므로 그대로 하드 일치.
    # - 쿼리에서 *추론*한 specialty 는 하드 배제 대신 '기타'를 함께 허용한다([추론, 기타]).
    #   본 제품의 정체성이 "표준 진료과목 *너머* 실제 주력"이라, HIRA 종별/이름파싱이 분류 못 해
    #   '기타'로 떨어진 모발이식·미용 부티크(=정작 그 쿼리의 핵심 병원)를 specialty 하드필터로
    #   배제하면 안 된다. 실측: "M자 탈모"→피부과 하드필터가 기타로 분류된 모엠·모우다·뉴셀
    #   (진짜 모발의원)을 통째 배제했고, '기타' 허용 시 정밀도 손실 없이 이들이 복귀.
    if query.specialty:
        specialty_filter: "str | list[str] | None" = query.specialty
    elif processed.inferred_specialty and processed.inferred_specialty != "기타":
        specialty_filter = [processed.inferred_specialty, "기타"]
    else:
        specialty_filter = processed.inferred_specialty  # None 또는 이미 '기타'
    if processed.was_expanded or processed.inferred_specialty:
        logger.info(
            "retrieve_hospital: 쿼리 전처리 — terms=%s specialty=%s expanded=%s",
            processed.medical_terms, processed.inferred_specialty, processed.was_expanded,
        )

    kb_id = os.environ.get("KB_ID")
    region = os.environ.get("AWS_REGION", "us-east-1")
    if not kb_id:
        raise KBRetrieveError("환경변수 KB_ID 가 설정되지 않았습니다.")

    client = boto3.client("bedrock-agent-runtime", region_name=region)

    # min-sim 임계 — 유사도가 너무 낮은(관련 없는) 결과 컷. 동의어 도배 제거 후 점수 분포가
    # 낮아지므로 보수적 기본값 + env 튜닝(KB_MIN_SCORE). 0 이면 비활성.
    min_score = float(os.environ.get("KB_MIN_SCORE", "0.3"))

    has_location = query.lat is not None and query.lng is not None

    # --- bounding box 계산 (위치 있을 때) ---
    lat_range: tuple[float, float] | None = None
    lng_range: tuple[float, float] | None = None
    if has_location:
        deg_offset = query.radius_km * _DEG_PER_KM
        lat_range = (query.lat - deg_offset, query.lat + deg_offset)  # type: ignore[operator]
        lng_range = (query.lng - deg_offset, query.lng + deg_offset)  # type: ignore[operator]

    # --- 1차 호출: 전체 필터 적용 (specialty 는 추론값+기타 보강) ---
    kb_filter = _build_kb_filter(
        sido=query.sido,
        sigungu=query.sigungu,
        specialty=specialty_filter,
        min_confidence=query.min_confidence,
        lat_range=lat_range,
        lng_range=lng_range,
    )

    # 한 병원이 self_claim/blog/reviews/vision 최대 4청크를 가지므로, limit*3 만 받으면
    # dedup 후 병원 수가 limit 에 한참 못 미친다(실측: limit10→30청크→dedup 10병원, min-sim
    # 컷 후 6병원). KB Retrieve 는 numberOfResults 가 30이든 100이든 단일 호출·동일 비용이라,
    # 항상 KB 최대(100)를 받아 dedup 풀을 키운다. 최종 출력은 어차피 query.limit 로 캡(아래).
    n_request = _KB_MAX_RESULTS
    raw = _kb_retrieve(client, kb_id, retrieve_text, kb_filter, n_request)

    # --- fallback: 빈 결과 시 지역/specialty/confidence 완화 (team_id 는 유지) ---
    if not raw and (query.sido or query.sigungu or specialty_filter or has_location):
        logger.info(
            "retrieve_hospital: 결과 0건 → 지역/specialty/min_confidence 필터 완화 fallback (query=%r)",
            q_text,
        )
        fallback_filter = _build_kb_filter()  # team_id 만 남김
        raw = _kb_retrieve(client, kb_id, retrieve_text, fallback_filter, n_request)

    if not raw:
        return []

    # --- hospital_id 기준 dedup (최고 score 1개) ---
    by_hospital = _dedup_by_hospital(raw)

    # --- haversine 재필터링 (위치 있을 때) ---
    if has_location:
        user_lat: float = query.lat  # type: ignore[assignment]
        user_lng: float = query.lng  # type: ignore[assignment]

        candidates: list[tuple[float, float, dict]] = []
        for item in by_hospital.values():
            md = item.get("metadata") or {}
            item_lat = md.get("lat")
            item_lng = md.get("lng")
            score = float(item.get("score") or 0.0)
            if item_lat is None or item_lng is None:
                # 좌표 없는 병원은 위치 검색에서 제외
                continue
            dist = _haversine_km(user_lat, user_lng, float(item_lat), float(item_lng))
            if dist <= query.radius_km and score >= min_score:
                candidates.append((dist, score, item))

        # 정렬
        if query.sort == "distance":
            candidates.sort(key=lambda x: x[0])
        elif query.sort == "confidence":
            candidates.sort(
                key=lambda x: float((x[2].get("metadata") or {}).get("confidence_score") or 0),
                reverse=True,
            )
        else:  # relevance (기본)
            candidates.sort(key=lambda x: x[1], reverse=True)

        results: list["SearchResult"] = []
        for dist_km, score, item in candidates[: query.limit]:
            results.append(
                _raw_to_search_result(
                    item,
                    similarity_score=round(score, 4),
                    distance_km=round(dist_km, 3),
                    query_interpretation=interpretation,
                )
            )
        return results

    # --- 자연어 단독 검색: min-sim 컷 후 정렬 ---
    kept = [it for it in by_hospital.values() if float(it.get("score") or 0.0) >= min_score]
    sorted_items = sorted(kept, key=lambda x: float(x.get("score") or 0.0), reverse=True)

    if query.sort == "confidence":
        sorted_items = sorted(
            kept,
            key=lambda x: float((x.get("metadata") or {}).get("confidence_score") or 0),
            reverse=True,
        )

    results = []
    for item in sorted_items[: query.limit]:
        score = float(item.get("score") or 0.0)
        results.append(
            _raw_to_search_result(
                item,
                similarity_score=round(score, 4),
                query_interpretation=interpretation,
            )
        )
    return results
