"""classify.py — 4 시그널 교차 검증으로 병원 주력 분야를 분류한다.

시그널 가중치:
  자칭 컨셉  25%  (사이트 메인·소개 텍스트 — 조작 가장 쉬움, 페널티 대상)
  Vision     30%  (시술 사진·기기 사진     — 위조 어려움, 가장 신뢰)
  블로그     20%  (포스팅 키워드 빈도      — 시간 누적된 행적)
  후기       25%  (후기·공공 데이터 키워드 — 외부 관점)

가중치 합계는 항상 100% 를 유지해야 한다. 변경 시 _WEIGHTS 딕셔너리만 수정하고
반드시 합이 1.0 인지 단위 테스트로 검증할 것.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone
from decimal import InvalidOperation
from typing import TYPE_CHECKING, Any

# bedrock_client 는 boto3 에 의존하므로 함수 호출 시점까지 import 를 지연한다.
# 이렇게 하면 boto3 없는 환경에서도 모듈 자체는 import 가능하고,
# @patch("ai.core.bedrock_client.invoke_model") mock 도 그대로 동작한다.
import importlib as _importlib

from ai.core.exceptions import BedrockInvocationError, InsufficientDataError
from shared.models import (
    BlogSignal,
    Classification,
    Confidence,
    CrawlData,
    DetailedSignals,
    ImageAnalysisResult,
    ReviewSignal,
    SelfClaimSignal,
    SignalContributions,
    VisionSignal,
    # 외부 플랫폼 시그널 타입 힌트용 (TYPE_CHECKING 없이 런타임 import — 순환 없음)
    GoogleReviews,
    KakaoPlace,
    KakaoReviews,
    NaverPlace,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 환경변수 / 상수
# ---------------------------------------------------------------------------

CLASSIFIER_VERSION = "v1.0"

CONFIDENCE_THRESHOLD_HIGH: int = int(os.getenv("CONFIDENCE_THRESHOLD_HIGH", "95"))
CONFIDENCE_THRESHOLD_LOW: int = int(os.getenv("CONFIDENCE_THRESHOLD_LOW", "70"))

# 근거 종류 수가 얇을 때(present 시그널 < MIN_CERTAIN_SIGNALS) score 상한.
# 교차검증 없이는 "확실" 불가 — 옛 룰 단독 70 cap 을 모든 경로로 일반화한 값.
CONFIDENCE_LEVEL1_CAP: int = int(os.getenv("CONFIDENCE_LEVEL1_CAP", "70"))
# "확실" 등급에 필요한 최소 present 시그널 종류 수 (교차 일치 천장 기준, 결정 5-1).
MIN_CERTAIN_SIGNALS: int = int(os.getenv("MIN_CERTAIN_SIGNALS", "2"))

# 시그널 가중치 — 합 반드시 1.0
_WEIGHTS: dict[str, float] = {
    "self_claim": 0.25,
    "vision":     0.30,
    "blog":       0.20,
    "reviews":    0.25,
}
assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9, "가중치 합이 1.0이 아닙니다"

# 자칭 도배 페널티 계수 (spam_score >= _SPAM_THRESHOLD 일 때 자칭 가중치에 곱함)
_SPAM_THRESHOLD: float = 0.7
_SPAM_PENALTY_FACTOR: float = 0.35  # 자칭 기여도를 35% 수준으로 강하게 감점

# 자칭 페이지 타입
# 자칭(self_claim) = 병원이 직접 쓴 것: 소개·진료안내 + 자체 blog 페이지(자체운영 블로그).
# 외부 제3자 후기 블로그(naver_blog 검색결과)는 별도 '블로그 시그널' 이라 여기 포함 안 함
# (저자 기준 분리 — 2026-05-30: 병원 자기 글 vs 남이 쓴 후기 블로그를 섞지 않는다).
_SELF_CLAIM_PAGE_TYPES = {"main", "about", "service", "blog"}

# (옛 _WEIGHTS_NO_VISION 제거: Vision 전용 재배분 대신 _cross_validate_signals 가
#  present 시그널 일반으로 가중치를 재분배한다. confidence-missing-signals 결정.)

# ---------------------------------------------------------------------------
# 분류 스키마 (M1 동결)
# ---------------------------------------------------------------------------

# 과목별 주력 후보 목록 — BE DynamoDB 컬럼·FE props의 기반. 임의 변경 금지.
SPECIALTY_FOCUS_SCHEMA: dict[str, list[str]] = {
    "피부과":    ["미용 시술", "일반 진료(아토피·여드름)", "피부암·종양", "모발·탈모"],
    "정형외과":  ["척추", "어깨·견관절", "무릎·관절", "손·발(수부외과)", "스포츠 의학"],
    "이비인후과": ["알레르기·비염", "청각·이명", "코·수면호흡", "갑상선"],
    "안과":     ["라식·라섹", "백내장", "망막", "일반 시력"],
}

# 과목 판별용 핵심 키워드 (우선순위 순)
_SPECIALTY_KEYWORDS: dict[str, list[str]] = {
    "피부과":    ["피부", "아토피", "여드름", "습진", "탈모", "보톡스", "필러", "레이저", "피부암"],
    "정형외과":  ["정형", "척추", "디스크", "어깨", "무릎", "관절", "골절", "스포츠"],
    "이비인후과": ["이비인후", "비염", "알레르기", "청각", "이명", "코골이", "갑상선"],
    "안과":     ["안과", "시력", "라식", "라섹", "백내장", "망막", "녹내장"],
}

# 의료 키워드 → 주력 분야 매핑
_KEYWORD_TO_FOCUS: dict[str, list[str]] = {
    # 피부과
    "보톡스":       ["미용 시술"],
    "필러":         ["미용 시술"],
    "리프팅":       ["미용 시술"],
    "피부 클리닉":  ["미용 시술"],
    "미용":         ["미용 시술"],
    "레이저":       ["미용 시술"],
    "아토피":       ["일반 진료(아토피·여드름)"],
    "여드름":       ["일반 진료(아토피·여드름)"],
    "습진":         ["일반 진료(아토피·여드름)"],
    "두드러기":     ["일반 진료(아토피·여드름)"],
    "사마귀":       ["일반 진료(아토피·여드름)"],
    "피부암":       ["피부암·종양"],
    "종양":         ["피부암·종양"],
    "흑색종":       ["피부암·종양"],
    "탈모":         ["모발·탈모"],
    "모발":         ["모발·탈모"],
    # 정형외과
    "척추":         ["척추"],
    "디스크":       ["척추"],
    "허리":         ["척추"],
    "어깨":         ["어깨·견관절"],
    "회전근개":     ["어깨·견관절"],
    "무릎":         ["무릎·관절"],
    "연골":         ["무릎·관절"],
    "손":           ["손·발(수부외과)"],
    "수근관":       ["손·발(수부외과)"],
    "스포츠":       ["스포츠 의학"],
    # 이비인후과
    "비염":         ["알레르기·비염"],
    "알레르기":     ["알레르기·비염"],
    "청각":         ["청각·이명"],
    "이명":         ["청각·이명"],
    "코골이":       ["코·수면호흡"],
    "수면":         ["코·수면호흡"],
    "갑상선":       ["갑상선"],
    # 안과
    "라식":         ["라식·라섹"],
    "라섹":         ["라식·라섹"],
    "스마일":       ["라식·라섹"],
    "백내장":       ["백내장"],
    "망막":         ["망막"],
    "황반":         ["망막"],
}


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 외부 시그널 입력 정규화
# ---------------------------------------------------------------------------

def _as_dict(obj) -> dict | None:
    """외부 시그널 입력을 dict 로 정규화한다.

    dict 또는 Pydantic 모델(model_dump 보유) 둘 다 수용한다.
    kb_store._as_dict 와 동일한 패턴 — boto3 의존 없이 classify.py 내부에 사본을 둔다.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    model_dump = getattr(obj, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return None


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 자칭 컨셉 추출
# ---------------------------------------------------------------------------

def _build_self_claim_prompt(combined_text: str) -> str:
    """자칭 컨셉 추출 프롬프트 생성.

    주체 명시 원칙을 지킨다: "이 병원이 자기 사이트에서 무엇을 메인으로 표시하는지"
    추출이 목표. 우리가 평가하지 않고 병원의 자기 표현을 그대로 읽는다.
    """
    return f"""다음은 한 병원 웹사이트의 메인·소개·진료안내 페이지 텍스트입니다.

이 병원이 자기 사이트에서 무엇을 메인으로 표시하고 있는지 분석해 주세요.

분석 원칙:
1. 병원이 스스로 강조하는 키워드와 주력 분야만 추출합니다.
2. 우리는 평가하지 않습니다. 병원이 자기 자신을 어떻게 표현했는지만 읽습니다.
3. 같은 키워드가 반복 등장할수록 spam_score를 높게 책정합니다.
   - spam_score 0.0: 자연스러운 단일 주제 설명
   - spam_score 0.5~0.7: 일부 키워드 반복 의심
   - spam_score 0.7~1.0: "전문" "특화" "전문클리닉" 같은 표현이 과도하게 반복됨

반환 형식 (JSON만 반환, 다른 텍스트 없이):
{{
  "keywords": ["키워드1", "키워드2", ...],
  "primary_focus": ["주력분야1", "주력분야2"],
  "spam_score": 0.0
}}

primary_focus는 아래 분류 스키마에서 선택하세요:
피부과: 미용 시술 / 일반 진료(아토피·여드름) / 피부암·종양 / 모발·탈모
정형외과: 척추 / 어깨·견관절 / 무릎·관절 / 손·발(수부외과) / 스포츠 의학
이비인후과: 알레르기·비염 / 청각·이명 / 코·수면호흡 / 갑상선
안과: 라식·라섹 / 백내장 / 망막 / 일반 시력

해당 분류에 없으면 가장 가까운 항목으로 표현하거나 빈 리스트로 반환하세요.

---
{combined_text[:8000]}
---"""


def _parse_llm_json(response: dict[str, Any]) -> dict[str, Any] | None:
    """Bedrock 응답 dict 에서 JSON 파싱. 실패 시 None 반환 (안전 fallback)."""
    try:
        content_blocks = response.get("content", [])
        if not content_blocks:
            return None
        raw_text: str = content_blocks[0].get("text", "")
        # 마크다운 코드블록 제거
        raw_text = re.sub(r"```(?:json)?", "", raw_text).strip()
        # 첫 번째 JSON 오브젝트만 추출
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            return None
        return json.loads(match.group())
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("LLM JSON 파싱 실패: %s", exc)
        return None


def _extract_self_claim(crawl_data: CrawlData) -> SelfClaimSignal:
    """자칭 컨셉 추출 — Bedrock Claude 호출.

    main / about / service 페이지 텍스트를 합쳐 LLM에 전달한다.
    Bedrock 호출 실패는 BedrockInvocationError 로 re-raise.
    JSON 파싱 실패 시 빈 SelfClaimSignal 로 안전 fallback.
    """
    target_pages = [
        p for p in crawl_data.pages
        if p.page_type in _SELF_CLAIM_PAGE_TYPES and p.html_text.strip()
    ]
    if not target_pages:
        logger.info("자칭 컨셉 추출 대상 페이지 없음 — 빈 SelfClaimSignal 반환")
        return SelfClaimSignal(keywords=[], primary_focus=[], spam_score=0.0)

    combined_text = "\n\n".join(
        f"[{p.page_type}] {p.url}\n{p.html_text}" for p in target_pages
    )
    prompt = _build_self_claim_prompt(combined_text)

    try:
        _bedrock = _importlib.import_module("ai.core.bedrock_client")
        response = _bedrock.invoke_model(prompt)
    except BedrockInvocationError:
        raise
    except Exception as exc:
        raise BedrockInvocationError(f"자칭 컨셉 추출 Bedrock 호출 실패: {exc}") from exc

    parsed = _parse_llm_json(response)
    if parsed is None:
        logger.warning("자칭 컨셉 JSON 파싱 실패 — 빈 SelfClaimSignal 반환")
        return SelfClaimSignal(keywords=[], primary_focus=[], spam_score=0.0)

    keywords: list[str] = parsed.get("keywords") or []
    primary_focus: list[str] = parsed.get("primary_focus") or []
    spam_score: float = float(parsed.get("spam_score", 0.0))
    spam_score = max(0.0, min(1.0, spam_score))

    return SelfClaimSignal(
        keywords=keywords,
        primary_focus=primary_focus,
        spam_score=spam_score,
    )


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 블로그 분석
# ---------------------------------------------------------------------------

_MEDICAL_KEYWORDS: list[str] = list(_KEYWORD_TO_FOCUS.keys())


def _count_medical_keywords(text: str) -> Counter:
    """텍스트에서 의료 키워드 빈도를 카운팅한다."""
    counter: Counter = Counter()
    for kw in _MEDICAL_KEYWORDS:
        count = text.count(kw)
        if count > 0:
            counter[kw] += count
    return counter


def _build_blog_prompt(combined_blog_text: str) -> str:
    """블로그 LLM 분석 프롬프트."""
    return f"""다음은 병원 공식 블로그 포스팅 텍스트들입니다.

이 병원 블로그가 주로 다루는 의료 주제를 분석해 주세요.

분석 목적:
- 사이트 자칭이 아닌, 실제 시간에 걸쳐 작성된 포스팅에서 주력 분야를 파악합니다.
- 포스팅 빈도와 주제 분포를 기반으로 판단합니다.

반환 형식 (JSON만 반환):
{{
  "primary_topics": ["주제1", "주제2"],
  "top_keywords": {{"키워드1": 빈도, "키워드2": 빈도}}
}}

primary_topics는 아래에서 선택:
미용 시술 / 일반 진료(아토피·여드름) / 피부암·종양 / 모발·탈모 /
척추 / 어깨·견관절 / 무릎·관절 / 손·발(수부외과) / 스포츠 의학 /
알레르기·비염 / 청각·이명 / 코·수면호흡 / 갑상선 /
라식·라섹 / 백내장 / 망막 / 일반 시력

---
{combined_blog_text[:10000]}
---"""


def _naver_blog_text(naver_blog) -> str:
    """네이버 블로그 posts 의 title + description 을 합쳐 반환 (키워드 추출 입력).

    naver_blog 는 NaverBlog 모델 또는 parse_naver_blog() dict. 없으면 "".
    작성자 PII 는 parse 단계에서 이미 제거됨.
    """
    nb = _as_dict(naver_blog)
    if not nb:
        return ""
    parts: list[str] = []
    for post in (nb.get("posts") or []):
        title = (post.get("title") or "") if isinstance(post, dict) else getattr(post, "title", "")
        desc = (post.get("description") or "") if isinstance(post, dict) else getattr(post, "description", "")
        if title or desc:
            parts.append(f"{title} {desc}".strip())
    return "\n".join(parts)


def _analyze_blog(crawl_data: CrawlData, naver_blog=None) -> BlogSignal:
    """블로그 키워드 분석.

    외부 제3자 후기 블로그(naver_blog)만 본다 — 자체 blog 페이지는 자칭(self_claim)으로
    귀속(저자 기준 분리). LLM 으로 주제 추출 + 키워드 카운팅 병행.
    """
    naver_text = _naver_blog_text(naver_blog)
    if not naver_text:
        return BlogSignal(total_posts=0, keyword_frequency={}, primary_topics=[])

    combined_text = naver_text
    keyword_counter = _count_medical_keywords(combined_text)

    # LLM 호출로 주제 추출 (실패 시 카운팅 결과만 사용)
    primary_topics: list[str] = []
    try:
        _bedrock = _importlib.import_module("ai.core.bedrock_client")
        prompt = _build_blog_prompt(combined_text)
        response = _bedrock.invoke_model(prompt)
        parsed = _parse_llm_json(response)
        if parsed:
            primary_topics = parsed.get("primary_topics") or []
            # LLM이 추출한 키워드 빈도도 병합
            llm_kw_freq: dict = parsed.get("top_keywords") or {}
            for kw, cnt in llm_kw_freq.items():
                try:
                    keyword_counter[str(kw)] += int(cnt)
                except (ValueError, TypeError):
                    pass
    except Exception as exc:
        logger.warning("블로그 LLM 분석 실패, 키워드 카운팅만 사용: %s", exc)

    # primary_topics 가 없으면 빈도 기반으로 추론
    if not primary_topics and keyword_counter:
        top_keywords = [kw for kw, _ in keyword_counter.most_common(5)]
        focus_votes: Counter = Counter()
        for kw in top_keywords:
            for focus in _KEYWORD_TO_FOCUS.get(kw, []):
                focus_votes[focus] += 1
        primary_topics = [f for f, _ in focus_votes.most_common(3)]

    nb = _as_dict(naver_blog)
    naver_post_count = len(nb.get("posts") or []) if nb else 0

    return BlogSignal(
        total_posts=naver_post_count,
        keyword_frequency=dict(keyword_counter.most_common(20)),
        primary_topics=primary_topics,
    )


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 후기 분석 (카카오·네이버·구글 외부 시그널)
# ---------------------------------------------------------------------------

def _analyze_reviews(
    kakao_reviews: "KakaoReviews | dict | None" = None,
    naver_reviews: "NaverPlace | dict | None" = None,
    google_reviews: "GoogleReviews | dict | None" = None,
) -> ReviewSignal:
    """외부 후기 시그널을 합산해 ReviewSignal 을 반환한다.

    세 인자 모두 None 이면 빈 시그널(하위 호환).
    각 인자는 dict 또는 대응 Pydantic 모델(KakaoReviews·NaverPlace·GoogleReviews) 둘 다 수용.

    키워드 빈도:
    - 카카오: keyword_frequency (strength 라벨 빈도 — "전문성"·"친절"·"주차"·"가격")
    - 네이버: keyword_stats (자체 추출 키워드 빈도)
    - 구글: keyword_frequency (자체 추출) + 없으면 리뷰 본문 text 에서 직접 추출

    후기 총수:
    - 카카오 total_reviews + 구글 user_ratings_total 합산.
    - 네이버 visitor_count 는 후기 수가 아니므로 제외.

    의료법 §56③ 준수:
    - 개별 후기 본문(contents/text)은 primary_topics 추출용 임시 입력으로만 사용.
    - ReviewSignal 어느 필드에도 후기 본문 raw 를 담지 않는다.
    """
    kakao_d = _as_dict(kakao_reviews)
    naver_d = _as_dict(naver_reviews)
    google_d = _as_dict(google_reviews)

    # 입력이 전혀 없으면 빈 시그널 (하위 호환)
    if kakao_d is None and naver_d is None and google_d is None:
        return ReviewSignal(total_reviews=0, keyword_frequency={}, primary_topics=[])

    merged_keyword_freq: Counter = Counter()

    # -- 카카오 키워드 빈도 합산 (strength 라벨: 전문성·친절 등 — 의료 focus 아님) --
    if kakao_d:
        for kw, cnt in (kakao_d.get("keyword_frequency") or {}).items():
            try:
                # DDB 는 숫자를 Decimal 로 줄 수 있어 int 변환 (NaN Decimal 은 InvalidOperation)
                merged_keyword_freq[str(kw)] += int(cnt)
            except (ValueError, TypeError, InvalidOperation):
                pass

    # -- 네이버 키워드 통계 합산 (비어 있으면 후기 본문에서 직접 추출 — 실측 사실 8:
    #    네이버는 병원 카테고리 키워드 통계를 주지 않으므로 keyword_stats 가 보통 빈 dict) --
    if naver_d:
        naver_kw = naver_d.get("keyword_stats") or {}
        if not naver_kw:
            review_items = naver_d.get("reviews") or []
            combined_naver_text = " ".join(
                (it.get("body") or "") if isinstance(it, dict) else getattr(it, "body", "")
                for it in review_items
            )
            naver_kw = dict(_count_medical_keywords(combined_naver_text))
        for kw, cnt in naver_kw.items():
            try:
                merged_keyword_freq[str(kw)] += int(cnt)
            except (ValueError, TypeError, InvalidOperation):
                pass

    # -- 구글 keyword_frequency 합산 (비어 있으면 리뷰 본문에서 직접 추출) --
    google_kw_freq: dict = {}
    if google_d:
        google_kw_freq = google_d.get("keyword_frequency") or {}
        if not google_kw_freq:
            # keyword_frequency 가 비어 있으면 리뷰 본문 text 에서 직접 추출
            review_items = google_d.get("reviews") or []
            combined_google_text = " ".join(
                (it.get("text") or "") if isinstance(it, dict) else getattr(it, "text", "")
                for it in review_items
            )
            google_kw_freq = dict(_count_medical_keywords(combined_google_text))
        for kw, cnt in google_kw_freq.items():
            try:
                merged_keyword_freq[str(kw)] += int(cnt)
            except (ValueError, TypeError, InvalidOperation):
                pass

    # -- 후기 총수 합산 (카카오 + 구글) --
    # DDB 는 숫자를 Decimal 로 주므로 isinstance(int) 체크 대신 안전 변환.
    def _safe_int(value) -> int:
        try:
            return int(value)
        except (ValueError, TypeError, InvalidOperation):
            return 0

    total_reviews = 0
    if kakao_d:
        total_reviews += _safe_int(kakao_d.get("total_reviews"))
    if google_d:
        total_reviews += _safe_int(google_d.get("user_ratings_total"))

    # -- primary_topics: 카카오·구글 후기 본문에서 의료 키워드 추출 후 focus 매핑 --
    # 의료법 §56③: 본문은 임시 입력으로만 사용, ReviewSignal 에는 저장하지 않음
    review_text_parts: list[str] = []
    if kakao_d:
        for item in (kakao_d.get("reviews") or []):
            contents = (
                item.get("contents") if isinstance(item, dict)
                else getattr(item, "contents", "")
            ) or ""
            review_text_parts.append(contents)
    if google_d:
        for item in (google_d.get("reviews") or []):
            text = (
                item.get("text") if isinstance(item, dict)
                else getattr(item, "text", "")
            ) or ""
            review_text_parts.append(text)
    if naver_d:
        for item in (naver_d.get("reviews") or []):
            body = (
                item.get("body") if isinstance(item, dict)
                else getattr(item, "body", "")
            ) or ""
            review_text_parts.append(body)

    primary_topics: list[str] = []
    if review_text_parts:
        combined_review_text = " ".join(review_text_parts)
        kw_counter = _count_medical_keywords(combined_review_text)
        focus_votes: Counter = Counter()
        for kw in [kw for kw, _ in kw_counter.most_common(5)]:
            for focus in _KEYWORD_TO_FOCUS.get(kw, []):
                focus_votes[focus] += 1
        primary_topics = [f for f, _ in focus_votes.most_common(3)]

    return ReviewSignal(
        total_reviews=total_reviews,
        keyword_frequency=dict(merged_keyword_freq.most_common(20)),
        primary_topics=primary_topics,
    )


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 카카오 tags 를 자칭 시그널에 합류
# ---------------------------------------------------------------------------

def _merge_kakao_tags_into_self_claim(
    signal: SelfClaimSignal,
    kakao_place: "KakaoPlace | dict | None" = None,
) -> SelfClaimSignal:
    """카카오 place tags 를 자칭 시그널에 병합한다.

    tags 는 카카오가 정제한 자칭 키워드라 사이트 텍스트보다 신호가 깨끗하다.
    - keywords·primary_focus 보강에만 사용
    - spam_score 는 사이트 텍스트 기준 그대로 유지 (과도한 페널티 방지)
    """
    kakao_d = _as_dict(kakao_place)
    if not kakao_d:
        return signal

    tags: list[str] = kakao_d.get("tags") or []
    if not tags:
        return signal

    # tags 를 의료 키워드 카운팅에 넣어 추가 기여 분 계산
    tags_text = " ".join(tags)
    tag_kw_counter = _count_medical_keywords(tags_text)

    # 기존 keywords 에 중복 없이 추가
    existing_kw_set = set(signal.keywords)
    extra_keywords: list[str] = []
    for kw, _ in tag_kw_counter.most_common():
        if kw not in existing_kw_set:
            extra_keywords.append(kw)
            existing_kw_set.add(kw)

    # primary_focus 보강 — 기존 focus 에 없는 항목만 추가
    existing_focus_set = set(signal.primary_focus)
    extra_focus: list[str] = []
    for kw in extra_keywords:
        for focus in _KEYWORD_TO_FOCUS.get(kw, []):
            if focus not in existing_focus_set:
                extra_focus.append(focus)
                existing_focus_set.add(focus)

    # 기존 tags 에서 직접 focus 스키마 항목 추출 (키워드 매핑 없이 직접 매핑 가능한 경우)
    # 예: tags 에 "추나요법" 같은 라벨이 있어도 _KEYWORD_TO_FOCUS 에 없으면 keyword 로만 보존
    extra_tags_not_in_kw: list[str] = []
    for tag in tags:
        if tag not in existing_kw_set:
            extra_tags_not_in_kw.append(tag)
            existing_kw_set.add(tag)

    new_keywords = signal.keywords + extra_keywords + extra_tags_not_in_kw
    new_primary_focus = signal.primary_focus + extra_focus

    return SelfClaimSignal(
        keywords=new_keywords,
        primary_focus=new_primary_focus,
        spam_score=signal.spam_score,  # spam_score 는 사이트 텍스트 기준 그대로
    )


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 표준 과목 추론
# ---------------------------------------------------------------------------

def _infer_standard_specialty(crawl_data: CrawlData) -> str:
    """크롤링 텍스트 + 공공 데이터에서 표준 진료과목을 추론한다."""
    # 공공 데이터의 전문의 자격에서 먼저 확인
    for specialist in (crawl_data.public_data.specialists if crawl_data.public_data else []):
        for specialty, keywords in _SPECIALTY_KEYWORDS.items():
            if any(kw in specialist for kw in keywords):
                return specialty

    # 전체 텍스트 키워드 빈도로 추론
    all_text = " ".join(
        p.html_text for p in crawl_data.pages if p.html_text
    )
    scores: Counter = Counter()
    for specialty, keywords in _SPECIALTY_KEYWORDS.items():
        for kw in keywords:
            scores[specialty] += all_text.count(kw)

    if scores:
        return scores.most_common(1)[0][0]
    return "기타"


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 자칭 도배 페널티
# ---------------------------------------------------------------------------

def _is_keyword_spamming(
    self_claim: SelfClaimSignal,
    blog: BlogSignal,
    reviews: ReviewSignal,
    vision: VisionSignal | None,
) -> bool:
    """자칭 도배 여부 판정.

    spam_score >= _SPAM_THRESHOLD 이고,
    나머지 시그널(블로그·후기·Vision)이 자칭 방향과 어긋나는지 확인한다.

    "어긋남" 기준:
    - 블로그 primary_topics 가 자칭 primary_focus 와 교집합이 없음
    - 후기 primary_topics 가 있으면 마찬가지로 교집합 없음
    - Vision image_categories 에 자칭 키워드 관련 카테고리 비율이 낮음
    """
    if self_claim.spam_score < _SPAM_THRESHOLD:
        return False
    if not self_claim.primary_focus:
        return False

    self_focus_set = set(self_claim.primary_focus)

    # 블로그 어긋남 체크
    blog_mismatch = (
        blog.total_posts > 0
        and len(self_focus_set & set(blog.primary_topics)) == 0
    )

    # 후기 어긋남 체크
    review_mismatch = (
        reviews.total_reviews > 0
        and len(self_focus_set & set(reviews.primary_topics)) == 0
    )

    # Vision 어긋남 체크 — 자칭 키워드가 Vision 카테고리에 없으면 어긋남
    vision_mismatch = False
    if vision is not None and vision.total_images_analyzed > 0:
        # 자칭 focus 가 미용 시술인데 Vision 에 관련 카테고리가 희박하면 도배 의심
        relevant_vision_ratio = sum(
            ratio for cat, ratio in vision.image_categories.items()
            if any(focus_kw in cat for focus_kw in self_claim.keywords[:5])
        )
        vision_mismatch = relevant_vision_ratio < 0.1

    # 블로그 또는 (후기 & Vision) 이 어긋나면 도배로 판정
    return blog_mismatch or (review_mismatch and vision_mismatch)


def _apply_spamming_penalty(
    contributions: dict[str, float | None],
) -> dict[str, float | None]:
    """자칭 도배 페널티 — 자칭 기여도를 _SPAM_PENALTY_FACTOR 로 감점한다.

    옛 설계는 자칭에서 깎은 만큼을 나머지 시그널로 재배분해 총합(1.0)을 보존했다.
    그러나 그 재배분은 **결손·엇갈림 시그널에 가짜 기여를 만들어** §3 원칙 3
    (가짜 비율 금지)과 충돌한다(예: 자칭과 어긋나는 블로그가 도리어 비중을 받음).
    이제 깎인 기여는 어디로도 재배분하지 않고 사라져 전체 score 가 내려간다 —
    자칭이 도배로 의심되고 다른 시그널이 이를 뒷받침하지 못하면 신뢰도가
    낮아지는 게 맞다.

    결손(None) 자칭은 감점 대상이 아니다(그대로 None 유지).
    """
    penalized = dict(contributions)
    self_contrib = penalized.get("self_claim")
    if self_contrib is not None:
        penalized["self_claim"] = self_contrib * _SPAM_PENALTY_FACTOR
    return penalized


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 4 시그널 교차 검증
# ---------------------------------------------------------------------------

def _topics_to_focus_votes(topics: list[str]) -> Counter:
    """주제 리스트를 focus 후보 투표 Counter 로 변환."""
    votes: Counter = Counter()
    for topic in topics:
        # 스키마에 직접 포함된 항목이면 그대로 1표
        for schema_items in SPECIALTY_FOCUS_SCHEMA.values():
            if topic in schema_items:
                votes[topic] += 1
        # 키워드 매핑 경유
        for focus in _KEYWORD_TO_FOCUS.get(topic, []):
            votes[focus] += 1
    return votes


def _is_present(signal_type: str, sig: Any) -> bool:
    """시그널이 **수집됨(present)** 인지 판정. 결손(미수집)과 구분한다.

    present 시그널만 score 풀과 등급 천장(coverage)에 들어간다. 여기서는
    데이터가 실제로 들어왔는지(coverage)만 본다 — top_focus 와 일치하는지(agreement)는
    _signal_alignment 가 0~1 로 별도 반영한다. "수집은 됐으나 엇갈림"은 present(=True)
    이면서 alignment 0 으로 표현된다.
    """
    if sig is None:
        return False
    if signal_type == "self_claim":
        return bool(sig.primary_focus) or bool(sig.keywords)
    if signal_type == "blog":
        return sig.total_posts > 0 or bool(sig.keyword_frequency)
    if signal_type == "reviews":
        return sig.total_reviews > 0 or bool(sig.keyword_frequency)
    if signal_type == "vision":
        return sig.total_images_analyzed > 0
    return False


def _cross_validate_signals(
    self_claim: SelfClaimSignal,
    blog: BlogSignal,
    reviews: ReviewSignal,
    vision: VisionSignal | None,
) -> tuple[list[str], dict[str, float | None]]:
    """4 시그널의 방향성 정렬 정도를 계산해 primary_focus 와 기여도를 반환한다.

    반환:
      primary_focus: list[str]  — 상위 주력 분야 (최대 3개)
      contributions: dict[str, float | None] — 시그널별 기여도(페널티 적용 전).
        * present 시그널: ``재분배 가중치 × top_focus 일치도`` (0~1).
          엇갈리면(일치도 0) 그대로 0 기여 — §1-1 의 0.5 베이스라인 제거.
        * 결손 시그널: ``None`` ("수집 안 됨"). 0(엇갈림)과 명시적으로 구분.
        present 시그널끼리 가중치를 재분배(합 1.0)하므로 결손은 점수에서 빠진다
        (반값도 0점도 아님 — §3 원칙 1).
    """
    # 각 시그널의 focus 투표 (결손 시그널은 빈 투표라 focus 선정에 0 기여)
    self_votes = _topics_to_focus_votes(self_claim.primary_focus)
    blog_votes = _topics_to_focus_votes(blog.primary_topics)
    review_votes = _topics_to_focus_votes(reviews.primary_topics)
    vision_votes: Counter = Counter()
    if vision is not None:
        # image_categories 의 카테고리명을 focus 로 매핑
        for cat, ratio in vision.image_categories.items():
            for focus in _KEYWORD_TO_FOCUS.get(cat, []):
                vision_votes[focus] += ratio
        # detected_devices 키워드도 반영
        device_kw_counter = _count_medical_keywords(
            " ".join(vision.detected_devices)
        )
        for kw, cnt in device_kw_counter.items():
            for focus in _KEYWORD_TO_FOCUS.get(kw, []):
                vision_votes[focus] += cnt * 0.5

    # 전체 후보 수집
    all_focus_candidates: set[str] = (
        set(self_votes.keys())
        | set(blog_votes.keys())
        | set(review_votes.keys())
        | set(vision_votes.keys())
    )

    def _normalize(counter: Counter) -> dict[str, float]:
        total = sum(counter.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in counter.items()}

    sc_norm = _normalize(self_votes)
    blog_norm = _normalize(blog_votes)
    rev_norm = _normalize(review_votes)
    vis_norm = _normalize(vision_votes)

    # 후보별 가중 점수 계산 — focus 선정엔 기본 _WEIGHTS 사용
    # (결손 시그널은 빈 norm 이라 가중치와 무관하게 0 기여 → 선정에 영향 없음).
    weighted_scores: dict[str, float] = {}
    for focus in all_focus_candidates:
        weighted_scores[focus] = (
            _WEIGHTS["self_claim"] * sc_norm.get(focus, 0.0)
            + _WEIGHTS["blog"]     * blog_norm.get(focus, 0.0)
            + _WEIGHTS["reviews"]  * rev_norm.get(focus, 0.0)
            + _WEIGHTS["vision"]   * vis_norm.get(focus, 0.0)
        )

    # 상위 3개 주력 분야 선정 (후보가 없으면 primary_focus=[], top_focus=None)
    sorted_focus = sorted(
        weighted_scores.items(), key=lambda x: x[1], reverse=True
    )
    primary_focus = [f for f, s in sorted_focus[:3] if s > 0.0]
    top_focus = primary_focus[0] if primary_focus else None

    def _signal_alignment(norm: dict[str, float]) -> float:
        """시그널이 top_focus 방향을 얼마나 지지하는지 (0~1)."""
        if top_focus is None or not norm:
            return 0.0
        return norm.get(top_focus, 0.0)

    align: dict[str, float] = {
        "self_claim": _signal_alignment(sc_norm),
        "blog":       _signal_alignment(blog_norm),
        "reviews":    _signal_alignment(rev_norm),
        "vision":     _signal_alignment(vis_norm),
    }

    # present 판정 — 수집된 시그널만 점수 풀에 남긴다 (§3 원칙 1).
    sig_objs: dict[str, Any] = {
        "self_claim": self_claim,
        "blog":       blog,
        "reviews":    reviews,
        "vision":     vision,
    }
    present = {k for k in _WEIGHTS if _is_present(k, sig_objs[k])}

    # present 끼리 가중치 재분배 (합 1.0). 결손은 풀에서 빠진다 → 점수 제외.
    norm_sum = sum(_WEIGHTS[k] for k in present)
    redistributed = (
        {k: _WEIGHTS[k] / norm_sum for k in present} if norm_sum > 0 else {}
    )

    contributions: dict[str, float | None] = {
        k: (redistributed[k] * align[k] if k in present else None)
        for k in _WEIGHTS
    }

    return primary_focus, contributions


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 신뢰도 계산
# ---------------------------------------------------------------------------

def _compute_confidence(
    contributions: dict[str, float | None],
) -> Confidence:
    """present 시그널 기여도 합으로 0~100 신뢰도 점수와 등급을 산정한다.

    confidence-missing-signals 결정 3원칙:
      1. 결손(None) 시그널은 점수 계산에서 **제외**(반값·0점 아님). present 끼리
         재분배된 기여도(_cross_validate_signals)만 합산한다.
      2. score 천장은 **present 시그널 종류 수**(coverage)로 제한 — present 가
         MIN_CERTAIN_SIGNALS 미만이면 "확실" 불가(CONFIDENCE_LEVEL1_CAP 상한).
         use_llm 분기 cap 을 이 천장으로 흡수·일반화했다.
      3. SignalContributions 는 결손을 ``None``("수집 안 됨")으로, present 는 일치
         기여 비율(%)로 채운다 — 가짜 비율 금지.

    Args:
        contributions: _cross_validate_signals(+페널티) 가 만든 시그널별 기여도.
            present 는 float(0~1), 결손은 None.
    """
    present = [k for k, v in contributions.items() if v is not None]
    n_present = len(present)

    if n_present == 0:
        # 진짜 아무것도 수집 못 함 → 정보 부족, 전 시그널 "수집 안 됨".
        return Confidence(
            score=0,
            level="정보 부족",
            signals=SignalContributions(),  # 전부 None 기본값
        )

    score_raw = sum(contributions[k] for k in present)  # 0~1
    score = max(0, min(100, int(round(score_raw * 100))))

    if n_present < MIN_CERTAIN_SIGNALS:
        # 근거 종류 수가 얇으면 "확실" 불가 — coverage 천장 (§3 원칙 2).
        score = min(score, CONFIDENCE_LEVEL1_CAP)
        level = "추정" if score >= CONFIDENCE_THRESHOLD_LOW else "정보 부족"
    elif score >= CONFIDENCE_THRESHOLD_HIGH:
        level = "확실"
    elif score >= CONFIDENCE_THRESHOLD_LOW:
        level = "추정"
    else:
        level = "정보 부족"

    # SignalContributions — 결손은 None("수집 안 됨"), present 는 일치 기여 비율(%).
    def _pct(value: float | None) -> int | None:
        if value is None:
            return None                       # 수집 안 됨 (가짜 비율 금지)
        if score_raw <= 0:
            return 0                           # present 지만 전부 엇갈림
        return int(round((value / score_raw) * 100))

    signals = SignalContributions(
        self_claim=_pct(contributions["self_claim"]),
        vision=_pct(contributions["vision"]),
        blog=_pct(contributions["blog"]),
        reviews=_pct(contributions["reviews"]),
    )

    return Confidence(score=score, level=level, signals=signals)


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 룰 기반 자칭 컨셉 추출 (LLM 미사용)
# ---------------------------------------------------------------------------

# 홍보성 어휘 목록 — spam_score 계산에 사용
_PROMO_WORDS: list[str] = [
    "전문", "특화", "전문클리닉", "최고", "유일", "명의", "1위", "최우수",
    "No.1", "NO.1", "no.1", "최다", "독보적", "탁월", "압도적",
]


def _extract_self_claim_rule(crawl_data: CrawlData) -> SelfClaimSignal:
    """자칭 컨셉 추출 — 룰 기반 (Bedrock 미호출).

    main / about / service 페이지의 html_text 합본에서
    _count_medical_keywords 로 키워드를 카운트하고,
    _KEYWORD_TO_FOCUS 로 primary_focus 를 매핑한다.

    spam_score 는 홍보성 어휘 밀도와 단일 키워드 과반복 비율로 산출한다.
    """
    target_pages = [
        p for p in crawl_data.pages
        if p.page_type in _SELF_CLAIM_PAGE_TYPES and p.html_text.strip()
    ]
    if not target_pages:
        logger.info("자칭 컨셉 추출 대상 페이지 없음 — 빈 SelfClaimSignal 반환 (룰)")
        return SelfClaimSignal(keywords=[], primary_focus=[], spam_score=0.0)

    combined_text = "\n\n".join(p.html_text for p in target_pages)
    keyword_counter = _count_medical_keywords(combined_text)

    # primary_focus: 빈도 상위 키워드를 _KEYWORD_TO_FOCUS 로 매핑 (중복 제거, 순서 유지)
    focus_seen: set[str] = set()
    primary_focus: list[str] = []
    keywords: list[str] = []
    for kw, _ in keyword_counter.most_common():
        keywords.append(kw)
        for focus in _KEYWORD_TO_FOCUS.get(kw, []):
            if focus not in focus_seen:
                focus_seen.add(focus)
                primary_focus.append(focus)

    # spam_score 계산
    # (1) 홍보성 어휘 밀도: 전체 글자 수 대비 홍보 어휘 등장 횟수
    promo_count = sum(combined_text.count(w) for w in _PROMO_WORDS)
    text_len = max(len(combined_text), 1)
    # 1000자당 홍보 어휘가 5회 이상이면 포화 상태(score 0.7+)로 간주
    promo_density = min(promo_count / (text_len / 1000), 5.0) / 5.0

    # (2) 단일 키워드 과반복 비율: 상위 1개 키워드가 전체 키워드 등장 합의 60% 초과
    total_kw_count = sum(keyword_counter.values())
    top_kw_count = keyword_counter.most_common(1)[0][1] if keyword_counter else 0
    dominance_ratio = (top_kw_count / total_kw_count) if total_kw_count > 0 else 0.0
    # dominance 0.6 이상이면 과반복으로 본다 (0.6→0.0, 1.0→0.4 스케일)
    dominance_score = max(0.0, (dominance_ratio - 0.6) / 0.4)

    spam_score = round(min(1.0, promo_density * 0.7 + dominance_score * 0.3), 4)

    return SelfClaimSignal(
        keywords=keywords,
        primary_focus=primary_focus,
        spam_score=spam_score,
    )


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 룰 기반 블로그 분석 (LLM 미사용)
# ---------------------------------------------------------------------------


def _analyze_blog_rule(crawl_data: CrawlData, naver_blog=None) -> BlogSignal:
    """블로그 키워드 분석 — 룰 기반 (Bedrock 미호출).

    **외부 제3자 후기 블로그**(네이버 블로그 검색 발췌)만 본다. 병원 자체 blog 페이지는
    자기가 쓴 것이라 자칭(self_claim)으로 귀속하므로 여기서 제외한다(저자 기준 분리).
    crawl_data 인자는 시그니처 호환용(자체 blog 는 이제 self_claim 으로 빠짐).
    """
    naver_text = _naver_blog_text(naver_blog)
    if not naver_text:
        return BlogSignal(total_posts=0, keyword_frequency={}, primary_topics=[])

    keyword_counter = _count_medical_keywords(naver_text)

    # primary_topics: 상위 5개 키워드를 focus 로 매핑 (중복 제거, 투표 순)
    focus_votes: Counter = Counter()
    for kw in [kw for kw, _ in keyword_counter.most_common(5)]:
        for focus in _KEYWORD_TO_FOCUS.get(kw, []):
            focus_votes[focus] += 1
    primary_topics = [f for f, _ in focus_votes.most_common(3)]

    nb = _as_dict(naver_blog)
    naver_post_count = len(nb.get("posts") or []) if nb else 0

    return BlogSignal(
        total_posts=naver_post_count,
        keyword_frequency=dict(keyword_counter.most_common(20)),
        primary_topics=primary_topics,
    )


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def classify_hospital(
    crawl_data: CrawlData,
    use_vision: bool = True,  # noqa: FBT001 — 명세에서 bool 파라미터로 정의됨
    use_llm: bool = True,     # noqa: FBT001 — False 이면 LLM/Vision 0회 호출 (트랙 A)
    *,
    standard_specialty: str | None = None,
    vision_results: list[ImageAnalysisResult] | None = None,
    kakao_place=None,
    kakao_reviews=None,
    kakao_blog=None,
    naver_reviews=None,
    naver_blog=None,
    google_reviews=None,
) -> Classification:
    """크롤링 데이터를 받아 4 시그널 교차 검증으로 병원 주력 분야를 분류한다.

    Args:
        crawl_data: BE 크롤러가 채워서 전달하는 크롤링 결과.
        use_vision: True 이면 Vision 시그널 포함. False 이면 비용 절감 모드.
            use_llm=False 일 때는 이 값과 무관하게 Vision 을 건너뛴다.
        use_llm: True 이면 자칭·블로그 추출에 Bedrock LLM 사용 (트랙 B/C).
            False 이면 키워드 룰만 사용하고 Bedrock 미호출 (트랙 A, 1만 풀커버).
        standard_specialty: HIRA 종별/병원명 기반 표준 진료과목(권위 값). 주어지면
            텍스트 키워드 추론(_infer_standard_specialty) 대신 이 값을 사용하고,
            해당 진료과의 시술 taxonomy 로 primary_focus 를 통제 어휘로 채운다.
            None 이면 기존처럼 크롤 텍스트로 추론(fallback).
        vision_results: 사전 계산된 Vision 분석 결과(ImageAnalysisResult 리스트).
            주어지면 이 값을 재사용하고 analyze_images 를 호출하지 않는다 — 시연 10개는
            run_vision_demo 가 DDB VISION#RESULTS 에 1회 적재하므로 분류기가 중복
            호출(비용 2배·결과 불일치)하지 않도록 호출자가 전달한다. None 이고
            use_llm·use_vision·이미지가 모두 있으면 analyze_images 로 직접 분석한다.
        kakao_place: KakaoPlace 모델 또는 parse_place() dict. tags 가 자칭 시그널 보강에 사용됨.
        kakao_reviews: KakaoReviews 모델 또는 parse_reviews() dict. strength 라벨 빈도 포함.
        kakao_blog: KakaoBlog 모델 또는 parse_blog() dict. (현재 미사용 — 향후 블로그 시그널 확장용)
        naver_reviews: NaverPlace 모델 또는 네이버 place dict. keyword_stats 포함.
        google_reviews: GoogleReviews 모델 또는 parse_google_reviews() dict.
            각 인자는 dict 또는 대응 Pydantic 모델 둘 다 수용한다.

    Returns:
        Classification: primary_focus, confidence, detailed_signals 포함.

    Raises:
        InsufficientDataError: 페이지가 0개이거나 모든 html_text 가 빈 문자열.
        BedrockInvocationError: Bedrock API 호출 실패 (use_llm=True 일 때만).
    """
    # 1. 데이터 유효성 검사 — 자체사이트가 비어도 외부 시그널이 있으면 분류한다.
    #    (병원 웹사이트는 필수 아님: 후기·블로그만으로도 주력을 추정. 둘 다 없을 때만 거부.)
    _has_site_text = bool(crawl_data.pages) and any(
        p.html_text.strip() for p in crawl_data.pages
    )
    _has_external = any(
        x is not None
        for x in (kakao_place, kakao_reviews, kakao_blog,
                  naver_reviews, naver_blog, google_reviews)
    )
    if not _has_site_text and not _has_external:
        raise InsufficientDataError(
            f"병원 {crawl_data.hospital_id}: 자체사이트·외부 시그널이 모두 없습니다."
        )

    # 2. 자칭 컨셉 추출
    if use_llm:
        self_claim_signal = _extract_self_claim(crawl_data)
    else:
        self_claim_signal = _extract_self_claim_rule(crawl_data)

    # 2-a. 카카오 tags 합류 — 정제된 자칭 키워드로 keywords·primary_focus 보강
    #       spam_score 는 사이트 텍스트 기준 그대로 유지 (과도한 페널티 방지)
    self_claim_signal = _merge_kakao_tags_into_self_claim(self_claim_signal, kakao_place)

    logger.info(
        "자칭 추출 완료 (%s) — focus=%s spam=%.2f",
        "LLM" if use_llm else "룰",
        self_claim_signal.primary_focus,
        self_claim_signal.spam_score,
    )

    # 3. Vision 분석 — use_llm=False 이면 무조건 건너뜀 (개인계정 Sonnet, 10개 한정)
    #                   use_vision=False 이면 건너뜀.
    #    vision_results 가 외부에서 주어지면(사전 계산된 VISION#RESULTS) 재사용해
    #    analyze_images 중복 호출(비용 2배·결과 불일치)을 피한다. 없을 때만 직접 분석.
    vision_signal: VisionSignal | None = None
    if use_llm and use_vision:
        results = vision_results
        if results is None and crawl_data.images:
            try:
                from ai.pipeline.vision import analyze_images  # type: ignore[import]

                image_urls = [img.url for img in crawl_data.images]
                max_images = int(os.getenv("MAX_VISION_IMAGES", "10"))
                results = analyze_images(image_urls[:max_images])
            except ImportError:
                logger.warning("ai.vision 모듈 없음 — Vision 시그널 건너뜀")
            except Exception as exc:
                logger.warning("Vision 분석 실패, 계속 진행: %s", exc)

        # ImageAnalysisResult 리스트를 VisionSignal 로 집계
        if results:
            cat_counter: Counter = Counter()
            all_devices: list[str] = []
            for r in results:
                cat_counter[r.image_category] += 1
                all_devices.extend(r.detected_devices)

            total = sum(cat_counter.values())
            image_categories = {
                cat: count / total for cat, count in cat_counter.items()
            }
            vision_signal = VisionSignal(
                detected_devices=list(set(all_devices)),
                image_categories=image_categories,
                total_images_analyzed=len(results),
            )

    # 4. 블로그 키워드 분석 — 자체 사이트 + 네이버 블로그 발췌 본문
    if use_llm:
        blog_signal = _analyze_blog(crawl_data, naver_blog)
    else:
        blog_signal = _analyze_blog_rule(crawl_data, naver_blog)
    logger.info(
        "블로그 분석 완료 (%s) — posts=%d topics=%s",
        "LLM" if use_llm else "룰",
        blog_signal.total_posts,
        blog_signal.primary_topics,
    )

    # 5. 후기 분석 — 외부 플랫폼 시그널(카카오·네이버·구글) 통합
    #    use_llm 분기와 무관하게 외부 후기 키워드는 룰·LLM 양 경로 모두 동일하게 적용
    review_signal = _analyze_reviews(kakao_reviews, naver_reviews, google_reviews)

    # 6. 4 시그널 교차 검증 — 결손은 None, present 끼리 재분배된 일치 기여도
    primary_focus, contributions = _cross_validate_signals(
        self_claim=self_claim_signal,
        blog=blog_signal,
        reviews=review_signal,
        vision=vision_signal,
    )
    logger.info("교차 검증 — primary_focus=%s contrib=%s", primary_focus, contributions)

    # 7. 자칭 도배 페널티 — 자칭 기여도만 감점(재배분 없음 → 총 score 하락)
    if _is_keyword_spamming(self_claim_signal, blog_signal, review_signal, vision_signal):
        logger.warning(
            "자칭 도배 의심 감지 (spam_score=%.2f) — 자칭 기여도 페널티 적용",
            self_claim_signal.spam_score,
        )
        contributions = _apply_spamming_penalty(contributions)

    # 8. 신뢰도 점수 계산 — 결손 제외·근거 종류 수 기반 등급 천장.
    #    "확실" 가부는 present 시그널 종류 수가 결정(결정 5-2: use_llm 분기 cap 폐지).
    #    룰 풀커버(1만)는 보통 자칭(+자체 blog 페이지)만 present 인데, 자체 블로그가
    #    있어도 본문이 여러 focus 로 흩어지면 일치도가 희석돼 score 가 HIGH 에 못 미친다.
    #    자칭·자체블로그가 단일 focus 로 또렷이 일치하는 병원만 룰 경로로도 확실 후보.
    confidence = _compute_confidence(contributions)
    logger.info(
        "신뢰도 계산 완료 — score=%d level=%s present=%s",
        confidence.score,
        confidence.level,
        [k for k, v in contributions.items() if v is not None],
    )

    # 9. 표준 과목 — HIRA 기준값(권위) 우선, 없으면 텍스트 추론 fallback
    final_specialty = standard_specialty or _infer_standard_specialty(crawl_data)

    # 9-a. 시술 태그(고정 taxonomy) — primary_focus 를 필터 가능한 통제 어휘로.
    #      진료과 taxonomy 에 매칭 태그가 있으면 그것으로 대체(닥터나우식 필터칩).
    #      taxonomy 미지원 종별(종합병원·요양병원 등)이거나 매칭 0이면 기존 추출 유지.
    from ai.search.taxonomy import tag_hospital  # boto3 무관, 순환 없음

    all_text = " ".join(p.html_text for p in crawl_data.pages if p.html_text)
    service_tags = tag_hospital(all_text, final_specialty)
    if service_tags:
        primary_focus = service_tags

    # 10. 최종 Classification 조립
    detailed_signals = DetailedSignals(
        self_claim=self_claim_signal,
        vision=vision_signal,
        blog=blog_signal,
        reviews=review_signal,
    )

    return Classification(
        hospital_id=crawl_data.hospital_id,
        standard_specialty=final_specialty,
        primary_focus=primary_focus,
        confidence=confidence,
        detailed_signals=detailed_signals,
        classified_at=datetime.now(tz=timezone.utc),
        classifier_version=CLASSIFIER_VERSION,
    )
