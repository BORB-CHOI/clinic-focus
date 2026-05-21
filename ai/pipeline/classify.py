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
    ReviewSignal,
    SelfClaimSignal,
    SignalContributions,
    VisionSignal,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 환경변수 / 상수
# ---------------------------------------------------------------------------

CLASSIFIER_VERSION = "v1.0"

CONFIDENCE_THRESHOLD_HIGH: int = int(os.getenv("CONFIDENCE_THRESHOLD_HIGH", "95"))
CONFIDENCE_THRESHOLD_LOW: int = int(os.getenv("CONFIDENCE_THRESHOLD_LOW", "70"))

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
_SELF_CLAIM_PAGE_TYPES = {"main", "about", "service"}

# Vision 없을 때 자칭·블로그·후기로 재배분하는 정규화 비율
_WEIGHTS_NO_VISION: dict[str, float] = {
    k: v / (1.0 - _WEIGHTS["vision"])
    for k, v in _WEIGHTS.items()
    if k != "vision"
}

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


def _analyze_blog(crawl_data: CrawlData) -> BlogSignal:
    """블로그 키워드 분석.

    LLM 호출로 주제를 추출하고, 단순 키워드 카운팅도 병행한다.
    블로그 페이지가 없으면 빈 BlogSignal(total_posts=0) 반환.
    """
    blog_pages = [
        p for p in crawl_data.pages
        if p.page_type == "blog" and p.html_text.strip()
    ]
    if not blog_pages:
        return BlogSignal(total_posts=0, keyword_frequency={}, primary_topics=[])

    combined_text = "\n\n".join(p.html_text for p in blog_pages)
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

    return BlogSignal(
        total_posts=len(blog_pages),
        keyword_frequency=dict(keyword_counter.most_common(20)),
        primary_topics=primary_topics,
    )


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 후기 분석 (현재 BE 미수집)
# ---------------------------------------------------------------------------

def _analyze_reviews() -> ReviewSignal:
    """후기 분석 — 현재 BE에서 후기 데이터를 아직 수집하지 않으므로 빈 시그널 반환."""
    return ReviewSignal(total_reviews=0, keyword_frequency={}, primary_topics=[])


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
    raw_contributions: dict[str, float],
) -> dict[str, float]:
    """자칭 도배 페널티 적용 — 자칭 기여도를 _SPAM_PENALTY_FACTOR 로 감점.

    자칭에서 깎인 만큼을 나머지 시그널에 비례 배분한다.
    결과 합은 원래 가중치 합(1.0)과 동일.
    """
    penalized = dict(raw_contributions)
    original_self = penalized["self_claim"]
    penalized["self_claim"] = original_self * _SPAM_PENALTY_FACTOR
    excess = original_self - penalized["self_claim"]

    # 나머지 시그널 비율로 재배분
    other_keys = [k for k in penalized if k != "self_claim"]
    other_sum = sum(penalized[k] for k in other_keys)
    if other_sum > 0:
        for k in other_keys:
            penalized[k] += excess * (penalized[k] / other_sum)
    else:
        # 나머지가 전부 0 이면 균등 배분
        share = excess / len(other_keys)
        for k in other_keys:
            penalized[k] += share

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


def _cross_validate_signals(
    self_claim: SelfClaimSignal,
    blog: BlogSignal,
    reviews: ReviewSignal,
    vision: VisionSignal | None,
) -> tuple[list[str], dict[str, float]]:
    """4 시그널의 방향성 정렬 정도를 계산해 primary_focus 와 기여도를 반환한다.

    반환:
      primary_focus: list[str]  — 상위 주력 분야 (최대 3개)
      raw_contributions: dict[str, float]  — 0~1 사이 기여도 (페널티 적용 전)
    """
    # 유효 가중치 계산 — Vision 없으면 재배분
    weights: dict[str, float]
    if vision is None:
        weights = _WEIGHTS_NO_VISION.copy()
        weights["vision"] = 0.0  # 계산 편의상 포함
    else:
        weights = dict(_WEIGHTS)

    # 각 시그널의 focus 투표
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

    if not all_focus_candidates:
        # 어떤 시그널도 후보를 만들지 못한 경우
        return [], {k: weights[k] for k in _WEIGHTS}

    # 후보별 가중 점수 계산
    def _normalize(counter: Counter) -> dict[str, float]:
        total = sum(counter.values())
        if total == 0:
            return {}
        return {k: v / total for k, v in counter.items()}

    sc_norm = _normalize(self_votes)
    blog_norm = _normalize(blog_votes)
    rev_norm = _normalize(review_votes)
    vis_norm = _normalize(vision_votes)

    weighted_scores: dict[str, float] = {}
    for focus in all_focus_candidates:
        score = (
            weights["self_claim"] * sc_norm.get(focus, 0.0)
            + weights["blog"]       * blog_norm.get(focus, 0.0)
            + weights["reviews"]    * rev_norm.get(focus, 0.0)
            + weights["vision"]     * vis_norm.get(focus, 0.0)
        )
        weighted_scores[focus] = score

    # 상위 3개 주력 분야 선정
    sorted_focus = sorted(
        weighted_scores.items(), key=lambda x: x[1], reverse=True
    )
    primary_focus = [f for f, _ in sorted_focus[:3] if _ > 0.0]

    # 시그널 기여도 계산 — 각 시그널이 primary_focus 방향으로 얼마나 정렬됐는지
    # primary_focus 상위 항목에 대한 각 시그널의 지지 비율 × 가중치
    top_focus = primary_focus[0] if primary_focus else None

    def _signal_alignment(norm: dict[str, float]) -> float:
        """시그널이 top_focus 방향을 얼마나 지지하는지 (0~1)."""
        if top_focus is None or not norm:
            return 0.0
        return norm.get(top_focus, 0.0)

    self_align = _signal_alignment(sc_norm)
    blog_align = _signal_alignment(blog_norm)
    rev_align = _signal_alignment(rev_norm)
    vis_align = _signal_alignment(vis_norm) if vision is not None else 0.0

    raw_contributions: dict[str, float] = {
        "self_claim": weights["self_claim"] * (0.5 + 0.5 * self_align),
        "blog":       weights["blog"]       * (0.5 + 0.5 * blog_align),
        "reviews":    weights["reviews"]    * (0.5 + 0.5 * rev_align),
        "vision":     weights["vision"]     * (0.5 + 0.5 * vis_align)
                      if vision is not None else 0.0,
    }

    return primary_focus, raw_contributions


# ---------------------------------------------------------------------------
# 내부 헬퍼 — 신뢰도 계산
# ---------------------------------------------------------------------------

def _compute_confidence(
    raw_contributions: dict[str, float],
    vision: VisionSignal | None,
) -> Confidence:
    """SignalContributions 합산 후 0~100 신뢰도 점수와 등급을 반환한다.

    Vision 이 없으면 vision 기여도는 0, 나머지가 100% 를 구성한다.
    """
    # 합산 전에 Vision 없는 경우 재정규화
    contrib = dict(raw_contributions)
    if vision is None:
        contrib["vision"] = 0.0
        other_sum = sum(v for k, v in contrib.items() if k != "vision")
        if other_sum > 0:
            scale = (1.0 - _WEIGHTS["vision"]) / other_sum if other_sum > 0 else 1.0
            for k in contrib:
                if k != "vision":
                    contrib[k] *= scale / (1.0 - _WEIGHTS["vision"])

    # 0~100 정수 기여도
    # 각 기여도는 해당 시그널 가중치(0~가중치) 범위 → 전체 합산 후 100 스케일
    total_raw = sum(contrib.values())
    # 최대 가능 점수는 1.0 (가중치 합). 실제 점수를 0~100 으로 스케일.
    score = int(round(min(total_raw, 1.0) * 100))
    score = max(0, min(100, score))

    if score >= CONFIDENCE_THRESHOLD_HIGH:
        level = "확실"
    elif score >= CONFIDENCE_THRESHOLD_LOW:
        level = "추정"
    else:
        level = "정보 부족"

    # SignalContributions — 각 시그널 기여도를 0~100 정수로 변환
    # 전체 score 합에서 각 시그널 비율을 정수 퍼센트로 표현
    def _to_int_pct(value: float) -> int:
        if total_raw == 0:
            return 0
        return int(round((value / total_raw) * 100))

    signals = SignalContributions(
        self_claim=_to_int_pct(contrib["self_claim"]),
        vision=_to_int_pct(contrib["vision"]),
        blog=_to_int_pct(contrib["blog"]),
        reviews=_to_int_pct(contrib["reviews"]),
    )

    return Confidence(score=score, level=level, signals=signals)


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def classify_hospital(
    crawl_data: CrawlData,
    use_vision: bool = True,  # noqa: FBT001 — 명세에서 bool 파라미터로 정의됨
) -> Classification:
    """크롤링 데이터를 받아 4 시그널 교차 검증으로 병원 주력 분야를 분류한다.

    Args:
        crawl_data: BE 크롤러가 채워서 전달하는 크롤링 결과.
        use_vision: True 이면 Vision 시그널 포함. False 이면 비용 절감 모드.

    Returns:
        Classification: primary_focus, confidence, detailed_signals 포함.

    Raises:
        InsufficientDataError: 페이지가 0개이거나 모든 html_text 가 빈 문자열.
        BedrockInvocationError: Bedrock API 호출 실패.
    """
    # 1. 데이터 유효성 검사
    if not crawl_data.pages:
        raise InsufficientDataError(
            f"병원 {crawl_data.hospital_id}: 크롤링된 페이지가 없습니다."
        )
    if all(not p.html_text.strip() for p in crawl_data.pages):
        raise InsufficientDataError(
            f"병원 {crawl_data.hospital_id}: 모든 페이지의 html_text 가 비어 있습니다."
        )

    # 2. 자칭 컨셉 추출 (Bedrock LLM)
    self_claim_signal = _extract_self_claim(crawl_data)
    logger.info(
        "자칭 추출 완료 — focus=%s spam=%.2f",
        self_claim_signal.primary_focus,
        self_claim_signal.spam_score,
    )

    # 3. Vision 분석 — use_vision=False 이거나 이미지 없으면 생략
    vision_signal: VisionSignal | None = None
    if use_vision and crawl_data.images:
        try:
            from ai.pipeline.vision import analyze_images  # type: ignore[import]

            image_urls = [img.url for img in crawl_data.images]
            max_images = int(os.getenv("MAX_VISION_IMAGES", "10"))
            vision_results = analyze_images(image_urls[:max_images])

            # ImageAnalysisResult 리스트를 VisionSignal 로 집계
            if vision_results:
                from collections import Counter as _Counter

                cat_counter: _Counter = _Counter()
                all_devices: list[str] = []
                for r in vision_results:
                    cat_counter[r.image_category] += 1
                    all_devices.extend(r.detected_devices)

                total = sum(cat_counter.values())
                image_categories = {
                    cat: count / total for cat, count in cat_counter.items()
                }
                vision_signal = VisionSignal(
                    detected_devices=list(set(all_devices)),
                    image_categories=image_categories,
                    total_images_analyzed=len(vision_results),
                )
        except ImportError:
            logger.warning("ai.vision 모듈 없음 — Vision 시그널 건너뜀")
        except Exception as exc:
            logger.warning("Vision 분석 실패, 계속 진행: %s", exc)

    # 4. 블로그 키워드 분석
    blog_signal = _analyze_blog(crawl_data)
    logger.info(
        "블로그 분석 완료 — posts=%d topics=%s",
        blog_signal.total_posts,
        blog_signal.primary_topics,
    )

    # 5. 후기 분석 (현재 빈 시그널)
    review_signal = _analyze_reviews()

    # 6. 4 시그널 교차 검증
    primary_focus, raw_contributions = _cross_validate_signals(
        self_claim=self_claim_signal,
        blog=blog_signal,
        reviews=review_signal,
        vision=vision_signal,
    )
    logger.info("교차 검증 — primary_focus=%s contrib=%s", primary_focus, raw_contributions)

    # 7. 자칭 도배 페널티
    if _is_keyword_spamming(self_claim_signal, blog_signal, review_signal, vision_signal):
        logger.warning(
            "자칭 도배 의심 감지 (spam_score=%.2f) — 자칭 기여도 페널티 적용",
            self_claim_signal.spam_score,
        )
        raw_contributions = _apply_spamming_penalty(raw_contributions)

    # 8. 신뢰도 점수 계산
    confidence = _compute_confidence(raw_contributions, vision_signal)
    logger.info(
        "신뢰도 계산 완료 — score=%d level=%s",
        confidence.score,
        confidence.level,
    )

    # 9. 표준 과목 추론
    standard_specialty = _infer_standard_specialty(crawl_data)

    # 10. 최종 Classification 조립
    detailed_signals = DetailedSignals(
        self_claim=self_claim_signal,
        vision=vision_signal,
        blog=blog_signal,
        reviews=review_signal,
    )

    return Classification(
        hospital_id=crawl_data.hospital_id,
        standard_specialty=standard_specialty,
        primary_focus=primary_focus,
        confidence=confidence,
        detailed_signals=detailed_signals,
        classified_at=datetime.now(tz=timezone.utc),
        classifier_version=CLASSIFIER_VERSION,
    )
