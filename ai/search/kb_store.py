"""kb_store.py — KB DataSource S3 업로드 + ingestion job 트리거 + KB Retrieve.

시그널별 청크 전략:
- 병원당 벡터 1개 ❌ → 시그널별 .txt 파일로 분리 (KB 파일 단위 청킹이 signal 경계 보존).
- signal_type ∈ {"self_claim", "blog", "reviews"}. 카카오 데이터는 각 signal 에 흡수.
- DESCRIPTION 은 임베딩 본문에 미포함 (상세페이지 표시용 별개).
- CLASSIFICATION 은 metadata 로만 (본문 아님).

S3 키 규약:
- 본문: {prefix}{hospital_id}/{signal_type}.txt
- 사이드카: {prefix}{hospital_id}/{signal_type}.txt.metadata.json

의료법 §56③:
- reviews 청크는 개별 후기 본문 본문 불포함. 키워드 빈도 요약만.

공개 함수:
- build_self_claim_chunk(crawl_data, kakao_place) -> str
- build_blog_chunk(crawl_data, kakao_blog) -> str
- build_reviews_chunk(kakao_reviews, naver_reviews, google_reviews) -> str
- build_signal_chunks(crawl_data, kakao_place, kakao_reviews, kakao_blog, naver_reviews, google_reviews) -> dict[str, str]
- build_ingest_metadata(meta, classification) -> dict
- ingest_hospital(hospital_id, signal_chunks, metadata, *, trigger_ingestion) -> None
- retrieve_hospital(query: SearchQuery) -> list[SearchResult]
"""

from __future__ import annotations

import json
import logging
import math
import os
from typing import TYPE_CHECKING

import boto3

if TYPE_CHECKING:
    from shared.models import (
        Classification,
        CrawlData,
        GoogleReviews,
        HospitalMeta,
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
    """후기 시그널 청크 — 키워드 빈도 요약만.

    의료법 §56③: 개별 후기 본문(contents) 텍스트는 절대 포함하지 않는다.
    "방문자 후기 강점 키워드 — 전문성 145회, 친절 164회, ..." 형태만.

    Args:
        kakao_reviews: parse_reviews() 출력 (KakaoReviews 모델 또는 dict). None 이면 생략.
        naver_reviews: NaverPlace 형태 (keyword_stats 키). 모델 또는 dict. None 이면 생략.
        google_reviews: parse_google_reviews() 출력 (GoogleReviews 또는 dict). None 이면 생략.

    Returns:
        키워드 빈도 요약 문자열. 데이터 없으면 "".
    """
    parts: list[str] = []
    kakao_reviews = _as_dict(kakao_reviews)
    naver_reviews = _as_dict(naver_reviews)
    google_reviews = _as_dict(google_reviews)

    # 카카오 후기 키워드 빈도
    if kakao_reviews:
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

    # 네이버 후기 키워드 빈도
    if naver_reviews:
        # NaverPlace 형태: keyword_stats: dict[str, int]
        ks: dict[str, int] = naver_reviews.get("keyword_stats") or {}
        if ks:
            ks_text = ", ".join(f"{k} {v}회" for k, v in sorted(ks.items(), key=lambda x: -x[1]))
            visitor_count = naver_reviews.get("visitor_count")
            header = "네이버 방문자 키워드"
            if visitor_count:
                header += f" (누적 방문 {visitor_count}명)"
            parts.append(f"{header} — {ks_text}")

    # 구글 리뷰 키워드 빈도
    if google_reviews:
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

    return "\n".join(parts)


def build_signal_chunks(
    crawl_data: "CrawlData | None" = None,
    kakao_place: "KakaoPlace | dict | None" = None,
    kakao_reviews: "KakaoReviews | dict | None" = None,
    kakao_blog: "KakaoBlog | dict | None" = None,
    naver_reviews: "NaverPlace | dict | None" = None,
    naver_blog: "NaverBlog | dict | None" = None,
    google_reviews: "GoogleReviews | dict | None" = None,
) -> dict[str, str]:
    """모든 시그널 청크를 조립하여 비어있지 않은 것만 반환.

    각 인자는 dict 또는 대응 Pydantic 모델(KakaoPlace 등) 둘 다 받는다.

    Returns:
        {signal_type: text} — signal_type ∈ {"self_claim", "blog", "reviews"}.
        빈 텍스트 시그널은 제외.
    """
    result: dict[str, str] = {}

    sc = build_self_claim_chunk(crawl_data=crawl_data, kakao_place=kakao_place)
    if sc:
        result["self_claim"] = sc

    bc = build_blog_chunk(crawl_data=crawl_data, kakao_blog=kakao_blog, naver_blog=naver_blog)
    if bc:
        result["blog"] = bc

    rc = build_reviews_chunk(
        kakao_reviews=kakao_reviews,
        naver_reviews=naver_reviews,
        google_reviews=google_reviews,
    )
    if rc:
        result["reviews"] = rc

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
    specialty: str | None = None,
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
        conditions.append({"equals": {"key": "standard_specialty", "value": specialty}})
    if min_confidence is not None:
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


def _raw_to_search_result(
    item: dict,
    similarity_score: float | None = None,
    distance_km: float | None = None,
) -> "SearchResult":
    """KB Retrieve raw result 항목을 SearchResult 로 변환한다."""
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
        query_interpretation=None,
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

    q_text = (query.query_text or "").strip()
    if not q_text:
        raise InvalidQueryError("retrieve_hospital: query_text 가 비어있습니다. KB Retrieve 는 빈 쿼리 불가.")

    kb_id = os.environ.get("KB_ID")
    region = os.environ.get("AWS_REGION", "us-east-1")
    if not kb_id:
        raise KBRetrieveError("환경변수 KB_ID 가 설정되지 않았습니다.")

    client = boto3.client("bedrock-agent-runtime", region_name=region)

    has_location = query.lat is not None and query.lng is not None

    # --- bounding box 계산 (위치 있을 때) ---
    lat_range: tuple[float, float] | None = None
    lng_range: tuple[float, float] | None = None
    if has_location:
        deg_offset = query.radius_km * _DEG_PER_KM
        lat_range = (query.lat - deg_offset, query.lat + deg_offset)  # type: ignore[operator]
        lng_range = (query.lng - deg_offset, query.lng + deg_offset)  # type: ignore[operator]

    # --- 1차 호출: 전체 필터 적용 ---
    kb_filter = _build_kb_filter(
        sido=query.sido,
        sigungu=query.sigungu,
        specialty=query.specialty,
        min_confidence=query.min_confidence,
        lat_range=lat_range,
        lng_range=lng_range,
    )

    # 같은 병원에서 여러 청크가 나올 수 있으므로 limit * 3 배로 넉넉히 요청
    n_request = min(query.limit * 3, _KB_MAX_RESULTS)
    raw = _kb_retrieve(client, kb_id, q_text, kb_filter, n_request)

    # --- fallback: 빈 결과 시 지역/specialty/confidence 완화 (team_id 는 유지) ---
    if not raw and (query.sido or query.sigungu or query.specialty or has_location):
        logger.info(
            "retrieve_hospital: 결과 0건 → 지역/specialty/min_confidence 필터 완화 fallback (query=%r)",
            q_text,
        )
        fallback_filter = _build_kb_filter()  # team_id 만 남김
        raw = _kb_retrieve(client, kb_id, q_text, fallback_filter, n_request)

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
            if dist <= query.radius_km:
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
                )
            )
        return results

    # --- 자연어 단독 검색: score 내림차순 정렬 ---
    sorted_items = sorted(
        by_hospital.values(),
        key=lambda x: float(x.get("score") or 0.0),
        reverse=True,
    )

    if query.sort == "confidence":
        sorted_items = sorted(
            by_hospital.values(),
            key=lambda x: float((x.get("metadata") or {}).get("confidence_score") or 0),
            reverse=True,
        )

    results = []
    for item in sorted_items[: query.limit]:
        score = float(item.get("score") or 0.0)
        results.append(_raw_to_search_result(item, similarity_score=round(score, 4)))
    return results
