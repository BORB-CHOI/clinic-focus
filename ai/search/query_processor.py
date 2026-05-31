"""
query_processor.py — 사용자 검색어를 임베딩에 적합한 형태로 정제·확장한다.

처리 단계 (단방향 파이프라인):
    1. ``normalize_query``    — 공백·특수문자 정리, 영문 lowercase
    2. ``tokenize``           — 화이트스페이스 + 한국어 보조 토큰화 (보수적)
    3. ``strip_stopwords``    — 검색 의도 표현(어디·추천·좋은 등) 제거
    4. ``extract_medical_terms`` — 의료 키워드 사전과 매칭 (multi-word 우선)
    5. ``infer_specialty``    — 매칭된 키워드로 표준 진료과목 추론 (최대 1개)
    6. ``expand_with_synonyms`` — 의학 동의어로 임베딩 입력 확장
    7. ``process_query``      — 위 단계를 묶어 ``ProcessedQuery`` 반환

설계 원칙:
- 입력 텍스트가 짧거나 의료 키워드를 못 찾아도 *원본을 그대로 임베딩*한다.
  사전이 부족해서 검색이 0건이 되는 사고를 막기 위함.
- 추론된 specialty 는 사용자가 명시한 ``specialty`` 가 없을 때만 적용.
- 토크나이저는 외부 의존성(KoNLPy 등) 없이 표준 라이브러리만 사용.
  한국어 형태소 분석 정확도가 필요하면 추후 mecab/kiwi 도입 검토.

테스트:
- ``ai/tests/test_query_processor.py`` 참조.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from ai.search.dictionaries import (
    KEYWORD_TO_FOCUS,
    KEYWORD_TO_SPECIALTY,
    STOPWORDS,
    SYNONYMS,
    VALID_SPECIALTIES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 정규식 패턴
# ---------------------------------------------------------------------------

# 한국어/영문/숫자/공백/일부 의료 표기(·, -)만 허용
_SAFE_CHARS = re.compile(r"[^\w\s가-힣·\-]+", re.UNICODE)
# 다중 공백 → 단일 공백
_MULTI_SPACE = re.compile(r"\s+")
# 영문 소문자 변환 대상
_ASCII_UPPER = re.compile(r"[A-Z]+")
# 한글 포함 여부 — 동의어 확장에서 순수 영어 의학용어를 걸러낼 때 사용
_HANGUL = re.compile(r"[가-힣]")


# ---------------------------------------------------------------------------
# 결과 타입
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProcessedQuery:
    """검색어 처리 결과.

    Attributes:
        original: 사용자 원본 입력.
        normalized: 정규화된 쿼리 (소문자·특수문자 제거).
        tokens: 불용어 제거 후 의미 토큰들.
        medical_terms: 사전과 매칭된 의료 키워드 목록 (등장 빈도 순).
        inferred_specialty: 추론된 표준 진료과목. None 이면 추론 실패.
        inferred_focus: 매칭된 키워드로부터 추정된 ``primary_focus`` 목록.
        embedding_text: 임베딩 호출 시 실제로 넘길 텍스트 (동의어 확장 포함).
        was_expanded: 동의어 확장이 적용됐는지 여부 (로깅·디버깅용).
    """

    original: str
    normalized: str
    tokens: list[str] = field(default_factory=list)
    medical_terms: list[str] = field(default_factory=list)
    inferred_specialty: str | None = None
    inferred_focus: list[str] = field(default_factory=list)
    embedding_text: str = ""
    was_expanded: bool = False


# ---------------------------------------------------------------------------
# 정규화·토큰화
# ---------------------------------------------------------------------------

def normalize_query(query: str) -> str:
    """검색어 정규화: 특수문자 제거 + 다중 공백 정리 + 영문 lowercase.

    의료 표기에 자주 쓰이는 ``·`` 와 하이픈 ``-`` 은 보존한다.
    """
    if not query:
        return ""
    # 특수문자 제거 (의료 표기 보존)
    cleaned = _SAFE_CHARS.sub(" ", query)
    # 영문 lowercase
    cleaned = _ASCII_UPPER.sub(lambda m: m.group(0).lower(), cleaned)
    # 다중 공백 정리
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()
    return cleaned


def tokenize(text: str) -> list[str]:
    """공백 단위 + 보조 분리 토큰화.

    한국어 형태소 분석기는 사용하지 않음. 의료 키워드 매칭은
    ``extract_medical_terms`` 에서 substring 기반으로 수행하므로 토큰화 정확도에
    의존하지 않는다. 본 함수는 불용어 필터링과 query_interpretation 표시용.
    """
    if not text:
        return []
    return [t for t in text.split() if t]


def strip_stopwords(tokens: list[str]) -> list[str]:
    """불용어를 제거한 토큰 리스트를 반환한다.

    완전 일치 + 어절 끝 조사 제거 (단순 휴리스틱):
    - "병원에서" → "병원에서" 자체가 STOPWORDS 에 없으면 어절 끝 조사 제거 시도.
    - **의료 키워드는 조사 분리 대상에서 제외** ("코골이" → "코골" 같은 손상 방지).
    - 그 외 어절은 길이 2~4 + 끝이 한국어 조사 1글자일 때만 분리 시도.

    Args:
        tokens: ``tokenize`` 결과.

    Returns:
        불용어와 빈 토큰이 제거된 리스트.
    """
    medical_kws = _all_medical_keywords_set()
    result: list[str] = []
    for tok in tokens:
        if not tok:
            continue
        if tok in STOPWORDS:
            continue
        # 의료 키워드 보호 — 조사 제거 휴리스틱이 의료 용어를 자르는 사고 방지
        if tok in medical_kws:
            result.append(tok)
            continue
        # 짧은 어절(2~4자)에 대해서만 한국어 조사 1글자 제거 시도
        if 2 <= len(tok) <= 4 and tok[-1:] in {"은", "는", "이", "가", "을", "를", "의", "도"}:
            stripped = tok[:-1]
            if stripped and stripped not in STOPWORDS:
                result.append(stripped)
                continue
            # 조사 제거 후 stopword 가 되면 그 토큰은 버림
            continue
        result.append(tok)
    return result


# ---------------------------------------------------------------------------
# 의료 키워드 추출
# ---------------------------------------------------------------------------

def extract_medical_terms(normalized: str) -> list[str]:
    """정규화된 쿼리에서 의료 키워드를 추출한다.

    - ``KEYWORD_TO_SPECIALTY`` + ``SYNONYMS`` 의 키 합집합이 매칭 대상.
    - multi-word 키워드("수면 무호흡" 등)를 우선 매칭하기 위해 길이 내림차순 정렬.
    - 동일 키워드 중복 매칭은 1회로 카운트.

    Returns:
        매칭된 키워드 리스트 (입력 순서 보존).
    """
    if not normalized:
        return []

    # 매칭 대상 키워드 합집합 — module-level 캐시
    keywords = _all_medical_keywords()

    found: list[tuple[int, str]] = []  # (position, keyword)
    for kw in keywords:
        idx = normalized.find(kw)
        if idx >= 0:
            found.append((idx, kw))

    # 위치 기준 정렬 후 중복 제거 (긴 키워드가 짧은 부분문자열을 덮을 수 있음)
    found.sort(key=lambda x: (x[0], -len(x[1])))
    seen: set[str] = set()
    result: list[str] = []
    consumed: list[tuple[int, int]] = []  # 이미 매칭된 구간 [start, end)
    for pos, kw in found:
        end = pos + len(kw)
        # 이미 더 긴 키워드가 이 구간을 덮었으면 skip
        if any(s <= pos and end <= e for s, e in consumed):
            continue
        if kw in seen:
            continue
        seen.add(kw)
        result.append(kw)
        consumed.append((pos, end))
    return result


# 모듈 레벨 캐시 — 사전이 클수록 매칭 시 길이 내림차순 정렬 비용 무시 못함.
_KEYWORD_CACHE: list[str] | None = None
_KEYWORD_SET_CACHE: set[str] | None = None


def _all_medical_keywords() -> list[str]:
    """``KEYWORD_TO_SPECIALTY`` ∪ ``SYNONYMS`` 키를 길이 내림차순으로 반환."""
    global _KEYWORD_CACHE
    if _KEYWORD_CACHE is None:
        merged = set(KEYWORD_TO_SPECIALTY.keys()) | set(SYNONYMS.keys())
        _KEYWORD_CACHE = sorted(merged, key=len, reverse=True)
    return _KEYWORD_CACHE


def _all_medical_keywords_set() -> set[str]:
    """O(1) lookup 용 set 캐시. ``strip_stopwords`` 의 의료 키워드 보호에 사용."""
    global _KEYWORD_SET_CACHE
    if _KEYWORD_SET_CACHE is None:
        _KEYWORD_SET_CACHE = set(KEYWORD_TO_SPECIALTY.keys()) | set(SYNONYMS.keys())
    return _KEYWORD_SET_CACHE


# ---------------------------------------------------------------------------
# Specialty / Focus 추론
# ---------------------------------------------------------------------------

# primary 가중 투표 파라미터 (infer_specialty).
# - 보조 과목 가중: 한 증상이 매핑된 2번째 이후 진료과의 표 무게. primary(1.0)보다
#   작아야 정준 과목이 단독 매핑을 못 이긴다. 0.4 → 보조 2개 합(0.8)도 primary 1개 못 넘음.
_SECONDARY_SPECIALTY_WEIGHT = 0.4
# - 확정 마진: 1위가 2위보다 이만큼 앞서야 확정. 미만이면 모호 → None(하드필터 안 걺).
#   0.5 → 단독 primary(1.0) vs 보조뿐(0.4) 은 통과, primary 동수(라식 vs 사마귀)는 차단.
_SPECIALTY_MARGIN = 0.5


def infer_specialty(medical_terms: list[str]) -> str | None:
    """매칭된 의료 키워드로부터 표준 진료과목을 추론한다.

    추론 알고리즘 (primary 가중 투표):
      1. 각 키워드의 진료과 리스트는 사전(.md) 섹션 순서대로이며 **첫 과목이 정준
         (primary)**. primary 1.0, 보조 0.4(``_SECONDARY_SPECIALTY_WEIGHT``) 가중 합산.
      2. 1위가 2위보다 ``_SPECIALTY_MARGIN`` 이상 앞서면 확정, 아니면 None(모호).
      3. 1위가 ``VALID_SPECIALTIES`` 에 있을 때만 반환.

    대용량 사전은 한 증상을 여러 과목에 매핑(아토피→피부과+소아+한의원)하므로 단순
    빈도 과반으로는 늘 None 이 된다. primary 가중으로 정준 과목을 띄우되, 동률/박빙은
    None — specialty 가 하드 메타필터라 오추론은 정답 병원을 통째 제외하기 때문.

    예시:
      - ["사마귀"]        → 피부과 1.0 → "피부과"
      - ["아토피"]        → 피부과 1.0 / 소아 0.4 / 한의원 0.4 → "피부과" (정준)
      - ["허리 디스크"]   → 정형외과 1.0 / 보조 0.4 → "정형외과"
      - ["라식", "사마귀"] → 안과 1.0 vs 피부과 1.0, 차 0 → None (모호)

    Args:
        medical_terms: ``extract_medical_terms`` 결과.

    Returns:
        추론된 진료과목 또는 None.
    """
    if not medical_terms:
        return None

    scores: Counter[str] = Counter()
    for term in medical_terms:
        for i, sp in enumerate(KEYWORD_TO_SPECIALTY.get(term, [])):
            scores[sp] += 1.0 if i == 0 else _SECONDARY_SPECIALTY_WEIGHT

    if not scores:
        return None

    ranked = scores.most_common()
    top_sp, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if top_sp not in VALID_SPECIALTIES:
        logger.warning("추론된 specialty 가 화이트리스트에 없음: %s", top_sp)
        return None

    if top_score - second_score < _SPECIALTY_MARGIN:
        logger.debug(
            "specialty 추론 모호 — 1위 %s(%.1f) vs 2위(%.1f) 차이 < %.1f. 후보: %s",
            top_sp, top_score, second_score, _SPECIALTY_MARGIN, dict(scores),
        )
        return None

    return top_sp


def infer_focus(medical_terms: list[str]) -> list[str]:
    """매칭된 키워드로부터 ``primary_focus`` 후보를 모은다.

    중복 제거하되 입력 순서 보존. 검색 메타필터로는 사용하지 않고
    ``query_interpretation`` 표시용.
    """
    seen: set[str] = set()
    result: list[str] = []
    for term in medical_terms:
        for focus in KEYWORD_TO_FOCUS.get(term, []):
            if focus not in seen:
                seen.add(focus)
                result.append(focus)
    return result


# ---------------------------------------------------------------------------
# 동의어 확장
# ---------------------------------------------------------------------------

def expand_with_synonyms(base_text: str, medical_terms: list[str]) -> tuple[str, bool]:
    """매칭된 의료 키워드의 동의어를 임베딩 입력에 부착한다.

    **순수 영어(한글 없는) 동의어는 제외한다.** 임베딩 코퍼스(병원 자체 사이트·후기·
    블로그)는 거의 전부 한국어라, ``alopecia``·``telogen effluvium`` 같은 영어 의학용어는
    어느 문서와도 직접 매칭되지 않고 쿼리 임베딩의 중심만 "일반 의학" 쪽으로 끌어당겨
    특화 의원(예: M자 탈모 → 모발이식 전문)을 순위에서 밀어낸다(실측: 영어 포함 시
    로코코성형 0.600 이 1위, 영어 제거 시 모엠·모아트 등 모발 전문의원이 상위로 복귀).
    ``M자 탈모``·``B형 간염`` 처럼 한글이 섞인 표기는 유효하므로 유지한다.

    Args:
        base_text: 정규화된 쿼리 (불용어 제거 전 — 의미 맥락 유지).
        medical_terms: ``extract_medical_terms`` 결과.

    Returns:
        (embedding_text, was_expanded) 쌍. 확장이 없으면 base_text 그대로.
    """
    if not medical_terms:
        return base_text, False

    expansions: list[str] = []
    seen: set[str] = set()
    for term in medical_terms:
        synonyms = SYNONYMS.get(term, [])
        for syn in synonyms:
            if syn in seen or syn in base_text:
                continue
            # 한글이 한 글자도 없는 동의어(순수 영어/라틴 의학용어)는 임베딩 노이즈 → 제외
            if not _HANGUL.search(syn):
                continue
            seen.add(syn)
            expansions.append(syn)

    if not expansions:
        return base_text, False

    # 임베딩 입력은 자연스러운 한 줄 형태. 동의어를 콤마+공백으로 부착.
    expanded = f"{base_text}, {', '.join(expansions)}"
    return expanded, True


# ---------------------------------------------------------------------------
# 통합 진입점
# ---------------------------------------------------------------------------

def process_query(query: str) -> ProcessedQuery:
    """사용자 검색어를 ``ProcessedQuery`` 로 변환한다.

    빈 입력이나 키워드 미매칭 시에도 ``embedding_text`` 는 항상 채워지므로
    호출자는 결과를 그대로 ``embed_text`` 에 넘길 수 있다.

    Examples:
        >>> r = process_query("사마귀 어디가 좋을까")
        >>> r.medical_terms
        ['사마귀']
        >>> r.inferred_specialty
        '피부과'
        >>> '심상성 우췌' in r.embedding_text
        True
    """
    if not query or not query.strip():
        return ProcessedQuery(original=query, normalized="", embedding_text="")

    normalized = normalize_query(query)
    tokens = tokenize(normalized)
    meaning_tokens = strip_stopwords(tokens)
    medical_terms = extract_medical_terms(normalized)

    # 임베딩 입력 = 의미 토큰 합본 (불용어 제거 효과).
    # 의미 토큰이 비면 정규화된 원문 사용 (사전이 빈약해도 검색은 굴러가야 함).
    base_text = " ".join(meaning_tokens) if meaning_tokens else normalized

    embedding_text, was_expanded = expand_with_synonyms(base_text, medical_terms)
    inferred_specialty = infer_specialty(medical_terms)
    inferred_focus = infer_focus(medical_terms)

    return ProcessedQuery(
        original=query,
        normalized=normalized,
        tokens=meaning_tokens,
        medical_terms=medical_terms,
        inferred_specialty=inferred_specialty,
        inferred_focus=inferred_focus,
        embedding_text=embedding_text,
        was_expanded=was_expanded,
    )
