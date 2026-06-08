"""의도-카테고리 정렬 프로토타입 — 질병 쿼리일 때 미용/성형 주력 병원을 강등.

임베딩 조작 없음. 이미 가진 메타데이터(primary_focus + 사전 주력분야)만 사용.
검색엔진의 vertical/intent 매칭을 모사. 콘솔 전용.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

import boto3  # noqa: E402

from ai.search.query_processor import process_query  # noqa: E402
from ai.search import kb_store  # noqa: E402

# 미용/성형 주력 라벨 (강남 실측 top focus 기반). 질병 쿼리에서 강등 대상.
COSMETIC = {
    "보톡스·필러", "리프팅·탄력", "리프팅·거상", "기미·색소", "미백·피부톤", "제모",
    "흉터·모공", "가슴성형", "눈성형", "코성형", "지방흡입·체형", "안면윤곽·양악",
    "한방피부·미용", "비만·다이어트", "비만·영양", "모발·탈모", "동안",
}


def _is_disease_query(p) -> bool:
    """쿼리 의도가 '질병/질환'인가 — 사전 주력분야에 '질환/감염/염'이 있으면 질병."""
    for f in p.inferred_focus:
        if any(k in f for k in ("질환", "감염", "염증", "자가면역")):
            return True
    return False


def _norm(f: str) -> str:
    """KB 메타 primary_focus 가 literal 따옴표로 감싸인 경우(\"보톡스·필러\") 정규화."""
    return f.strip().strip('"').strip("'").strip()


def _cosmetic_ratio(pf: list[str]) -> float:
    if not pf:
        return 0.0
    return sum(1 for f in pf if _norm(f) in COSMETIC) / len(pf)


def measure(query_text: str, term: str):
    p = process_query(query_text)
    disease = _is_disease_query(p)
    client = boto3.client("bedrock-agent-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    kb_filter = kb_store._build_kb_filter(
        specialty=[p.inferred_specialty, "기타"] if p.inferred_specialty else None)
    raw = kb_store._kb_retrieve(client, os.environ["KB_ID"], p.embedding_text, kb_filter, 100)
    min_score = float(os.environ.get("KB_MIN_SCORE", "0.42"))
    groups = kb_store._aggregate_by_hospital(raw, p.medical_terms)
    rows = [g for g in groups.values() if g["max_score"] >= min_score]

    W_COSMETIC = 0.08  # 질병 쿼리에서 미용주력 강등 강도
    for g in rows:
        md = g["best"].get("metadata") or {}
        g["name"] = md.get("name", "?")
        g["sp"] = md.get("standard_specialty", "?")
        g["pf"] = kb_store._parse_focus(md)
        g["cos_ratio"] = _cosmetic_ratio(g["pf"])
        g["fi"] = kb_store._focus_intensity(g)
        # 질병 쿼리면 미용비율만큼 강등
        g["fi_intent"] = g["fi"] - (W_COSMETIC * g["cos_ratio"] if disease else 0.0)

    print("=" * 104)
    print(f"QUERY {query_text!r}  의도={'질병(강등 적용)' if disease else '미용/일반(강등 없음)'}  "
          f"focus={p.inferred_focus}")
    print("=" * 104)
    cur = sorted(rows, key=lambda g: -g["fi"])
    new = sorted(rows, key=lambda g: -g["fi_intent"])
    print(f"  {'[현재 순위]':<48}  {'[의도정렬 순위]'}")
    for i in range(min(8, len(rows))):
        a, b = cur[i], new[i]
        amark = "🔴" if a["cos_ratio"] >= 0.8 else ("🟡" if a["cos_ratio"] >= 0.5 else "🟢")
        bmark = "🔴" if b["cos_ratio"] >= 0.8 else ("🟡" if b["cos_ratio"] >= 0.5 else "🟢")
        print(f"  {i+1}.{amark}{a['name'][:13]:<13}({a['sp'][:4]}) 미용{a['cos_ratio']*100:3.0f}%"
              f"   →  {bmark}{b['name'][:13]:<13}({b['sp'][:4]}) 미용{b['cos_ratio']*100:3.0f}%")
    print()


if __name__ == "__main__":
    for q, t in [("무좀", "무좀"), ("아토피", "아토피"), ("여드름", "여드름")]:
        measure(q, t)
