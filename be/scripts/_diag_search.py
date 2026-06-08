"""무좀 검색 근본원인 진단 — 일회성. retrieve_hospital 내부를 계측해 병원별 raw 점수 해부.

검색 결과로 본문 노출 안 함(콘솔 진단 전용). 끝나면 삭제.
"""
from __future__ import annotations

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


def diag(query_text: str, *, use_specialty_filter: bool = True, topn: int = 15):
    print("=" * 90)
    print(f"QUERY: {query_text!r}   (specialty_filter={'ON' if use_specialty_filter else 'OFF(team_id만)'})")
    print("=" * 90)
    p = process_query(query_text)
    print(f"  medical_terms      = {p.medical_terms}")
    print(f"  inferred_specialty = {p.inferred_specialty}")
    print(f"  inferred_focus     = {p.inferred_focus}")
    print(f"  embedding_text     = {p.embedding_text!r}")
    print(f"  was_expanded       = {p.was_expanded}")

    kb_id = os.environ["KB_ID"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-agent-runtime", region_name=region)

    _GENERALIST = {"기타", "가정의학과"}
    if use_specialty_filter and p.inferred_specialty and p.inferred_specialty not in _GENERALIST:
        specialty_filter = [p.inferred_specialty, "기타"]
    else:
        specialty_filter = None
    kb_filter = kb_store._build_kb_filter(specialty=specialty_filter)
    print(f"  specialty_filter   = {specialty_filter}")

    retrieve_text = p.embedding_text or query_text
    raw = kb_store._kb_retrieve(client, kb_id, retrieve_text, kb_filter, kb_store._KB_MAX_RESULTS)
    print(f"  KB raw chunks      = {len(raw)}")

    min_score = float(os.environ.get("KB_MIN_SCORE", "0.42"))
    groups = kb_store._aggregate_by_hospital(raw, p.medical_terms)

    rows = []
    for hid, g in groups.items():
        md = g["best"].get("metadata") or {}
        # best 청크의 signal_type 추정: content/location 에서 추출
        loc = g["best"].get("location") or {}
        s3uri = (loc.get("s3Location") or {}).get("uri", "") if isinstance(loc, dict) else ""
        signal = s3uri.rsplit("/", 1)[-1].replace(".txt", "") if s3uri else "?"
        rows.append({
            "name": md.get("name", "?"),
            "sp": md.get("standard_specialty", "?"),
            "pf": kb_store._parse_focus(md),
            "max_score": g["max_score"],
            "mentions": g["mentions"],
            "n_chunks": g["n_chunks"],
            "pf_match": g["pf_match"],
            "fi": kb_store._focus_intensity(g),
            "best_signal": signal,
            "kept": g["max_score"] >= min_score,
        })

    rows.sort(key=lambda r: -r["fi"])
    kept = [r for r in rows if r["kept"]]
    print(f"  min-sim({min_score}) 통과 = {len(kept)} / {len(rows)} 병원")
    print(f"\n  {'rk':>2} {'fi':>6} {'cos':>6} {'men':>3} {'nch':>3} {'pfm':>3} {'sig':>10}  name (sp) [pf...]")
    for i, r in enumerate(kept[:topn], 1):
        pf = ", ".join(r["pf"][:4])
        print(f"  {i:>2} {r['fi']:.4f} {r['max_score']:.4f} {r['mentions']:>3} "
              f"{r['n_chunks']:>3} {str(r['pf_match'])[0]:>3} {r['best_signal']:>10}  "
              f"{r['name']} ({r['sp']}) [{pf}]")
    print()


if __name__ == "__main__":
    queries = sys.argv[1:] or ["무좀"]
    for q in queries:
        diag(q)
