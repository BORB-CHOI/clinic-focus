"""
검색어 처리 지식사전 — 데이터는 ``ai/data/medical_dictionary.json`` 에 있고
본 모듈은 **loader** 다 (PR #33 후속, 2026-05-29 데이터 외부화).

왜 외부 데이터 파일인가:
- 의료 전문가가 코드 변경 없이 사전(.json)만 PR 로 수정·확장 가능.
- 특정 케이스 하드코딩이 아니라 "지식사전" 으로 운영 — 진료과별로 계속 채워나감.
- ``dictionaries.py`` 는 로드·정규화·캐시만 담당.

소비처 (둘 다 같은 사전을 씀 — 단일 출처):
- ``query_processor.py`` — **쿼리 측** 확장·진료과 추론 (사용자 입력 → 본문 매칭).
- ``kb_store.py`` (``_enrich_with_synonyms``) — **문서 측** 주입. 병원 청크에 동의어
  클러스터를 부착해 본문이 "심상성 우췌"라고만 적혀 있어도 "사마귀" 쿼리에 매칭됨.

설계 원칙 (사전 추가 시 지킬 것):
- ``synonyms`` 는 *일반어(키) → 본문 학명·전문용어·영문·치료(값)* 단방향으로 채운다.
  문서-측 주입은 키·값을 묶어 양방향 클러스터로 변환해 쓰므로 한쪽만 채우면 된다.
- ``stopwords`` 에 의료 용어 절대 금지 (임베딩 의미 신호 손실).
- **의료법 §56 회색지대**: 평가·광고 표현("잘하는", "최고", "전문", "효과") 절대 금지.
  사전이 광고성 표현을 담으면 검색 결과 자체가 회색지대를 끌어당긴다.
- ``standard_specialty`` 는 22 후보 한정 (ai/CLAUDE.md "분류 스키마").

JSON 스키마: {version, note, stopwords[], synonyms{}, keyword_to_specialty{},
keyword_to_focus{}, valid_specialties[]}.
"""

from __future__ import annotations

import json
from pathlib import Path

# ai/data/medical_dictionary.json — 본 파일(ai/search/) 기준 한 단계 위의 data/.
_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "medical_dictionary.json"


def _load() -> dict:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_RAW = _load()

DICTIONARY_VERSION: str = _RAW.get("version", "unknown")

# ---------------------------------------------------------------------------
# 검색 의도 표현 (불용어) — 의미 검색 노이즈. 의료 용어 미포함.
# ---------------------------------------------------------------------------
STOPWORDS: frozenset[str] = frozenset(_RAW["stopwords"])

# ---------------------------------------------------------------------------
# 의학 동의어 (일반어 → 본문 학명·전문용어·영문·치료). 쿼리 확장 + 문서 주입 양용.
# ---------------------------------------------------------------------------
SYNONYMS: dict[str, list[str]] = {k: list(v) for k, v in _RAW["synonyms"].items()}

# ---------------------------------------------------------------------------
# 의료 키워드 → 표준 진료과목 22 매핑 (한 키가 복수 과목 가능, 추론 시 다수결).
# ---------------------------------------------------------------------------
KEYWORD_TO_SPECIALTY: dict[str, list[str]] = {
    k: list(v) for k, v in _RAW["keyword_to_specialty"].items()
}

# ---------------------------------------------------------------------------
# 의료 키워드 → primary_focus (자유 문자열, 메타필터 아님 — query_interpretation 표시용).
# ---------------------------------------------------------------------------
KEYWORD_TO_FOCUS: dict[str, list[str]] = {
    k: list(v) for k, v in _RAW["keyword_to_focus"].items()
}

# ---------------------------------------------------------------------------
# 진료과목 화이트리스트 (메타필터 specialty 검증용). ai/CLAUDE.md 22 후보와 동기화.
# ---------------------------------------------------------------------------
VALID_SPECIALTIES: frozenset[str] = frozenset(_RAW["valid_specialties"])


# ---------------------------------------------------------------------------
# 동의어 클러스터 — 문서-측 주입용 양방향 그룹.
#
# SYNONYMS 는 단방향(일반어→학명)이지만, 문서(병원 청크)에는 어느 표현이 적혀
# 있을지 모른다. {키 + 값} 을 한 클러스터로 묶어, 청크에 클러스터의 *아무* 멤버라도
# 있으면 나머지 멤버를 부착한다 → 양방향 매칭.
# ---------------------------------------------------------------------------

def build_synonym_clusters() -> list[list[str]]:
    """SYNONYMS 를 {키 + 값} 단위 클러스터 리스트로 변환한다.

    각 클러스터는 같은 개념의 동의어 묶음. 문서-측 주입(_enrich_with_synonyms)이
    "청크에 멤버 1개라도 있으면 나머지 부착" 에 사용한다.
    """
    return [[key, *values] for key, values in SYNONYMS.items()]
