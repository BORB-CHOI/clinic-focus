"""
검색어 처리 지식사전 — 데이터는 사람이 읽고 편집하는 마크다운
``ai/data/medical_dictionary.md`` 에 있고, 본 모듈은 그 .md 를 파싱하는 **loader** 다.

왜 마크다운 지식사전인가:
- 의료 전문가가 코드 없이 .md 표만 보고 PR 로 항목을 추가·수정 (진료과별 섹션).
- 특정 케이스 하드코딩이 아니라 22 진료과 전반을 덮는 "대용량 지식사전" 으로 운영.
- ``dictionaries.py`` 는 파싱·정규화·캐시만.

소비처:
- ``query_processor.py`` — **쿼리 측** 확장·진료과 추론 (사용자 입력 → 본문 매칭).
  사전은 **사용자 쿼리만** 확장한다. 병원 청크(문서 측)에는 주입하지 않는다 — doc-side
  주입은 트리거 단어 1회만으로 무관 진료과 동의어를 끌어들여 임베딩 변별력을 파괴해
  제거됨(치과가 "M자 탈모" 1위 사고, 2026-05-31).

마크다운 형식 (loader 가 이 규약을 파싱):
    ## 불용어
    어디, 추천, 좋은, 병원, ...        (쉼표 구분, 여러 줄 가능)

    ## 진료과: 피부과
    | 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
    |---|---|---|
    | 사마귀 | 심상성 우췌, verruca, 냉동치료 | 일반 진료(아토피·여드름) |

- ``## 진료과: {표준진료과목}`` 섹션의 표 한 행 = 사전 1항목.
  · 1열 일반어 = 키, 2열 = 동의어(쉼표 구분), 3열 = primary_focus(선택).
  · 같은 일반어가 여러 진료과 섹션에 나오면 진료과·동의어가 병합된다(예: 보톡스 → 피부과+성형외과).
- 셀 안에 ``|`` 금지(표 구분자와 충돌). 동의어 구분은 쉼표.

설계 원칙(항목 추가 시):
- **의료법 §56**: 평가·광고·효능 표현("잘하는·최고·전문·효과·탁월·완치") 절대 금지.
  질환명·해부학·시술명·검사명·학명·영문 같은 사실 정보만.
- ``standard_specialty`` 는 22 후보 한정(아래 VALID_SPECIALTIES).
"""

from __future__ import annotations

import re
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "medical_dictionary.md"

# ai/CLAUDE.md "분류 스키마" 22 후보군과 동기화 (메타필터 specialty 검증·섹션 인식).
VALID_SPECIALTIES: frozenset[str] = frozenset({
    "내과", "소아청소년과", "이비인후과", "안과", "피부과", "성형외과",
    "정형외과", "신경외과", "외과", "산부인과", "비뇨의학과",
    "정신건강의학과", "가정의학과", "재활의학과", "마취통증의학과", "신경과",
    "한의원", "치과",
    "종합병원", "요양병원", "보건소", "기타",
})

_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$")
_SPECIALTY_HEADER_RE = re.compile(r"^##\s+진료과:\s*(.+?)\s*$")


def _split_csv(cell: str) -> list[str]:
    return [t.strip() for t in cell.split(",") if t.strip()]


def _parse() -> dict:
    """medical_dictionary.md 를 파싱해 사전 구조를 만든다."""
    stopwords: set[str] = set()
    synonyms: dict[str, list[str]] = {}
    kw_to_specialty: dict[str, list[str]] = {}
    kw_to_focus: dict[str, list[str]] = {}
    version = "unknown"

    text = _DATA_PATH.read_text(encoding="utf-8")

    # 버전 (> 최종 업데이트: YYYY-MM-DD 형태가 있으면 추출)
    m = re.search(r"최종 업데이트[:\s]+(\d{4}-\d{2}-\d{2})", text)
    if m:
        version = m.group(1)

    section: str | None = None       # "불용어" | specialty | None
    cur_specialty: str | None = None

    def _add(d: dict[str, list[str]], key: str, vals: list[str]) -> None:
        cur = d.setdefault(key, [])
        for v in vals:
            if v and v not in cur:
                cur.append(v)

    for raw in text.splitlines():
        line = raw.rstrip()
        sp_m = _SPECIALTY_HEADER_RE.match(line)
        if sp_m:
            cur_specialty = sp_m.group(1).strip()
            section = "specialty" if cur_specialty in VALID_SPECIALTIES else None
            continue
        h_m = _HEADER_RE.match(line)
        if h_m:
            section = "불용어" if h_m.group(1).strip().startswith("불용어") else None
            cur_specialty = None
            continue

        if section == "불용어":
            if line.strip() and not line.startswith(">"):
                stopwords.update(_split_csv(line))
            continue

        if section == "specialty" and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2:
                continue
            common = cells[0]
            # 헤더행·구분행 스킵
            if not common or common in ("일반어",) or set(common) <= {"-", ":", " "}:
                continue
            syns = _split_csv(cells[1]) if len(cells) >= 2 else []
            focus = cells[2].strip() if len(cells) >= 3 else ""
            _add(synonyms, common, syns)
            _add(kw_to_specialty, common, [cur_specialty])  # type: ignore[list-item]
            if focus:
                _add(kw_to_focus, common, [focus])

    return {
        "version": version,
        "stopwords": stopwords,
        "synonyms": synonyms,
        "keyword_to_specialty": kw_to_specialty,
        "keyword_to_focus": kw_to_focus,
    }


_PARSED = _parse()

DICTIONARY_VERSION: str = _PARSED["version"]
STOPWORDS: frozenset[str] = frozenset(_PARSED["stopwords"])
SYNONYMS: dict[str, list[str]] = _PARSED["synonyms"]
KEYWORD_TO_SPECIALTY: dict[str, list[str]] = _PARSED["keyword_to_specialty"]
KEYWORD_TO_FOCUS: dict[str, list[str]] = _PARSED["keyword_to_focus"]
