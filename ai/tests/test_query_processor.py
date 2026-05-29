"""query_processor 단위 테스트.

검증 포인트:
- 정규화 (특수문자·공백·대소문자)
- 불용어 제거 (의료 용어는 보존)
- 의료 키워드 추출 (multi-word 우선)
- specialty 자동 추론 (모호성 임계값)
- 동의어 확장 (임베딩 입력에 의학 학명 부착)
- 빈 입력·매칭 0건 fallback (검색이 굴러가야 함)

본 테스트는 boto3 의존성이 전혀 없으므로 로컬에서 ``pytest`` 즉시 실행 가능.
"""

from __future__ import annotations

import pytest

from ai.search.query_processor import (
    ProcessedQuery,
    expand_with_synonyms,
    extract_medical_terms,
    infer_focus,
    infer_specialty,
    normalize_query,
    process_query,
    strip_stopwords,
    tokenize,
)


# ---------------------------------------------------------------------------
# normalize_query
# ---------------------------------------------------------------------------

class TestNormalizeQuery:
    def test_strips_special_chars(self):
        assert normalize_query("사마귀!? 어디???") == "사마귀 어디"

    def test_collapses_whitespace(self):
        assert normalize_query("사마귀   치료    병원") == "사마귀 치료 병원"

    def test_lowercases_ascii(self):
        assert normalize_query("LASIK 라식") == "lasik 라식"

    def test_preserves_medical_punctuation(self):
        # · 와 - 는 의료 표기에서 흔하므로 보존
        result = normalize_query("어깨·견관절 통증")
        assert "·" in result

    def test_empty_input(self):
        assert normalize_query("") == ""
        assert normalize_query("   ") == ""


# ---------------------------------------------------------------------------
# tokenize / strip_stopwords
# ---------------------------------------------------------------------------

class TestTokenization:
    def test_strips_question_intent(self):
        tokens = tokenize("사마귀 어디가 좋을까")
        meaningful = strip_stopwords(tokens)
        # "어디가", "좋을까" 는 STOPWORDS 에 직접 등록 → 제거
        assert "사마귀" in meaningful
        assert "어디가" not in meaningful
        assert "좋을까" not in meaningful

    def test_preserves_medical_term_with_josa(self):
        # "탈모는" 4자 + 끝이 "는" → 조사 제거 시도 → "탈모" 보존
        tokens = tokenize("탈모는 어디가")
        meaningful = strip_stopwords(tokens)
        assert "탈모" in meaningful

    def test_strips_general_noun_stopwords(self):
        # "병원", "추천" 은 stopword 라 결과는 의료 키워드만 남음
        tokens = tokenize("강남 피부과 병원 추천")
        meaningful = strip_stopwords(tokens)
        assert "병원" not in meaningful
        assert "추천" not in meaningful

    def test_empty_input(self):
        assert tokenize("") == []
        assert strip_stopwords([]) == []


# ---------------------------------------------------------------------------
# extract_medical_terms
# ---------------------------------------------------------------------------

class TestExtractMedicalTerms:
    def test_extracts_single_term(self):
        terms = extract_medical_terms("사마귀")
        assert "사마귀" in terms

    def test_extracts_multiple_terms(self):
        terms = extract_medical_terms("사마귀 탈모 보톡스")
        assert set(terms) >= {"사마귀", "탈모", "보톡스"}

    def test_empty_query_returns_empty(self):
        assert extract_medical_terms("") == []

    def test_no_match_returns_empty(self):
        assert extract_medical_terms("hello world") == []

    def test_multi_word_keyword_priority(self):
        # "여드름 흉터"(multi-word)가 "여드름"보다 길어 우선 매칭되어야 함
        terms = extract_medical_terms("여드름 흉터 치료 상담")
        assert "여드름 흉터" in terms
        # 더 긴 키워드가 구간을 덮으므로 "여드름" 단독은 중복 매칭 안 됨
        assert "여드름" not in terms

    def test_substring_dedup(self):
        # 동일 키워드가 두 번 나타나도 1회 카운트
        terms = extract_medical_terms("사마귀 사마귀 사마귀")
        assert terms.count("사마귀") == 1


# ---------------------------------------------------------------------------
# infer_specialty
# ---------------------------------------------------------------------------

class TestInferSpecialty:
    def test_unique_specialty_returns_it(self):
        assert infer_specialty(["사마귀"]) == "피부과"

    def test_strong_majority_returns_winner(self):
        # 사마귀(피부과 primary) + 아토피(피부과 primary) + 라식(안과 primary)
        # → 피부과 2.0 vs 안과 1.0, 차 1.0 ≥ 마진 → 피부과
        assert infer_specialty(["사마귀", "아토피", "라식"]) == "피부과"

    def test_multi_specialty_term_resolves_to_primary(self):
        # 대용량 사전은 한 증상을 여러 과목에 매핑(허리 디스크 → 정형외과+신경외과+…).
        # primary 가중으로 정준 과목(정형외과)이 보조 과목들을 이긴다.
        assert infer_specialty(["허리 디스크"]) == "정형외과"
        assert infer_specialty(["아토피"]) == "피부과"

    def test_ambiguous_returns_none(self):
        # 라식(안과 primary) + 사마귀(피부과 primary) → 1.0:1.0 동률 → None (하드필터 안 걺)
        assert infer_specialty(["라식", "사마귀"]) is None

    def test_ambiguous_chronic_returns_none(self):
        # 당뇨·고혈압은 내과·가정의학과 양쪽이 관리 → 모호 → None (한쪽으로 오제외 안 함)
        from ai.search.query_processor import process_query
        assert process_query("당뇨 고혈압 관리").inferred_specialty is None

    def test_empty_returns_none(self):
        assert infer_specialty([]) is None

    def test_unknown_term_returns_none(self):
        assert infer_specialty(["없는키워드"]) is None


# ---------------------------------------------------------------------------
# infer_focus
# ---------------------------------------------------------------------------

class TestInferFocus:
    def test_extracts_focus(self):
        # 사마귀의 focus(자유 문자열, 표시용) — 사전 값이 비어있지 않아야
        focuses = infer_focus(["사마귀"])
        assert focuses and all(isinstance(f, str) and f for f in focuses)

    def test_dedups_focus(self):
        # 아토피 + 습진 모두 "염증·알레르기 피부질환" focus 공유 → 1회만
        focuses = infer_focus(["아토피", "습진"])
        assert focuses.count("염증·알레르기 피부질환") == 1


# ---------------------------------------------------------------------------
# expand_with_synonyms
# ---------------------------------------------------------------------------

class TestSynonymExpansion:
    def test_expands_with_known_term(self):
        text, expanded = expand_with_synonyms("사마귀", ["사마귀"])
        # 동의어 사전에서 알려진 학명이 포함돼야 함
        assert expanded is True
        assert "심상성 우췌" in text

    def test_no_expansion_when_no_terms(self):
        text, expanded = expand_with_synonyms("사마귀", [])
        assert expanded is False
        assert text == "사마귀"

    def test_skips_synonyms_already_in_text(self):
        # 본문에 이미 "심상성 우췌" 가 있으면 중복 추가 안 함
        base = "사마귀 심상성 우췌"
        text, _ = expand_with_synonyms(base, ["사마귀"])
        # "심상성 우췌" 가 1회만 등장해야 함
        assert text.count("심상성 우췌") == 1


# ---------------------------------------------------------------------------
# process_query — 통합 테스트
# ---------------------------------------------------------------------------

class TestProcessQuery:
    def test_problem_case_사마귀_어디가_좋을까(self):
        """리포트된 문제 케이스 — 정확도 회귀 방지."""
        result = process_query("사마귀 어디가 좋을까")

        assert isinstance(result, ProcessedQuery)
        # 의료 키워드 추출 OK
        assert "사마귀" in result.medical_terms
        # 진료과 추론 성공
        assert result.inferred_specialty == "피부과"
        # focus 추론 성공 (자유 문자열 — 사전 라벨에 의존하지 않고 비어있지 않음만 검증)
        assert result.inferred_focus
        # 동의어 확장 적용
        assert result.was_expanded is True
        assert "심상성 우췌" in result.embedding_text
        # 불용어 제거 — "어디가", "좋을까" 는 embedding_text 에 직접 표현으로 안 남음
        # (단, 동의어 확장 결과에는 포함될 수 있어 직접 검증 어려움 → tokens 만 검증)
        assert "어디가" not in result.tokens
        assert "좋을까" not in result.tokens

    def test_empty_input(self):
        result = process_query("")
        assert result.medical_terms == []
        assert result.inferred_specialty is None
        assert result.embedding_text == ""

    def test_no_medical_terms_falls_through(self):
        """매칭 0건이어도 정규화된 원문으로 임베딩 가능해야 함."""
        result = process_query("그냥 평범한 문장입니다")
        assert result.medical_terms == []
        assert result.inferred_specialty is None
        # 매칭이 없어도 embedding_text 는 비어선 안 됨
        assert result.embedding_text != ""

    def test_explicit_medical_query(self):
        """다중 키워드 쿼리: 추천 의도 표현 제거 + 진료과 자동 추론."""
        result = process_query("강남에서 라식 백내장 잘하는 안과 추천")
        # "라식" + "백내장" 모두 안과 매칭 → 안과 추론
        assert result.inferred_specialty == "안과"
        # "추천", "잘하는" 같은 평가성 표현은 토큰에서 빠져야 함
        assert "추천" not in result.tokens
        assert "잘하는" not in result.tokens

    def test_specialty_ambiguous_returns_none(self):
        """모호 케이스: specialty 추론 실패 시 None — 메타필터로 잘못 걸지 않음."""
        # "라식"(안과) 1개 vs "사마귀"(피부과) 1개 → 1:1 → None
        result = process_query("라식 사마귀")
        assert result.inferred_specialty is None
        # 그래도 동의어 확장과 medical_terms 추출은 정상 작동
        assert set(result.medical_terms) >= {"라식", "사마귀"}
        assert result.was_expanded is True

    @pytest.mark.parametrize("query,expected_specialty", [
        ("허리 디스크 잘하는 곳", "정형외과"),
        ("아토피 좋은 병원", "피부과"),
        ("코골이 잘 보는 곳", "이비인후과"),
        ("임플란트 추천", "치과"),
        ("라식 백내장 안과", "안과"),
        ("전립선 비대 방광염", "비뇨의학과"),
    ])
    def test_specialty_inference_matrix(self, query: str, expected_specialty: str):
        """대표 쿼리 매트릭스 — 각 진료과별로 추론이 올바른지 회귀 방지.

        (당뇨·고혈압 같은 내과/가정의학과 양과 관리 질환은 의도적으로 제외 —
         모호 → None 이 안전한 동작이라 test_ambiguous_chronic_returns_none 에서 별도 검증.)
        """
        result = process_query(query)
        assert result.inferred_specialty == expected_specialty, (
            f"쿼리 '{query}' → 기대 {expected_specialty}, 실제 {result.inferred_specialty}"
        )
