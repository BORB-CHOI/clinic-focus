"""근접중복 청크 제거 fingerprint 실험 — 보일러플레이트(네비 메뉴) collapse 검증. 콘솔 전용."""
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


def _fingerprint(text: str) -> frozenset:
    """길이>1 토큰의 집합 — 같은 메뉴가 약간씩 어긋나 잘려도 토큰집합은 거의 동일."""
    toks = [t for t in text.split() if len(t) > 1]
    return frozenset(toks)


def _near_dup(fp: frozenset, seen: list[frozenset], thresh: float = 0.8) -> bool:
    for s in seen:
        if not fp or not s:
            continue
        inter = len(fp & s)
        jac = inter / len(fp | s)
        if jac >= thresh:
            return True
    return False


def measure(query_text: str, term: str):
    p = process_query(query_text)
    client = boto3.client("bedrock-agent-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    kb_filter = kb_store._build_kb_filter(
        specialty=[p.inferred_specialty, "기타"] if p.inferred_specialty else None
    )
    raw = kb_store._kb_retrieve(client, os.environ["KB_ID"], p.embedding_text, kb_filter, 100)
    min_score = float(os.environ.get("KB_MIN_SCORE", "0.42"))

    agg: dict[str, dict] = {}
    for r in raw:
        md = r.get("metadata") or {}
        hid = md.get("hospital_id")
        if not hid:
            continue
        score = float(r.get("score") or 0.0)
        content = r.get("content") or {}
        text = content.get("text", "") if isinstance(content, dict) else str(content)
        g = agg.setdefault(hid, {
            "name": md.get("name", "?"), "sp": md.get("standard_specialty", "?"),
            "pf": kb_store._parse_focus(md), "max_score": 0.0,
            "raw_m": 0, "raw_nch": 0, "dd_m": 0, "dd_nch": 0, "seen": [],
        })
        g["max_score"] = max(g["max_score"], score)
        c = text.count(term)
        g["raw_m"] += c
        g["raw_nch"] += 1
        fp = _fingerprint(text)
        if not _near_dup(fp, g["seen"]):
            g["seen"].append(fp)
            g["dd_m"] += c
            g["dd_nch"] += 1

    wpf, wfreq, wchunk = 0.06, 0.010, 0.010

    def fi(mscore, pfm, m, nch):
        return mscore + (wpf if pfm else 0) + wfreq * math.log1p(m) + wchunk * math.log1p(max(0, nch - 1))

    rows = [g for g in agg.values() if g["max_score"] >= min_score]
    for g in rows:
        terms = p.medical_terms
        g["pfm"] = any(t in str(x) for t in terms for x in g["pf"])
        g["fi_raw"] = fi(g["max_score"], g["pfm"], g["raw_m"], g["raw_nch"])
        g["fi_dd"] = fi(g["max_score"], g["pfm"], g["dd_m"], g["dd_nch"])

    print("=" * 100)
    print(f"QUERY {query_text!r}  (통과 {len(rows)})   raw=현재  dd=근접중복제거")
    print("=" * 100)
    print("  [현재 raw 순위]                          →  [중복제거 순위]")
    cur = sorted(rows, key=lambda g: -g["fi_raw"])
    new = sorted(rows, key=lambda g: -g["fi_dd"])
    for i in range(min(8, len(rows))):
        a, b = cur[i], new[i]
        print(f"  {i+1}. {a['name'][:14]:<14} fi={a['fi_raw']:.4f} m{a['raw_m']}/c{a['raw_nch']}"
              f"   →  {b['name'][:14]:<14} fi={b['fi_dd']:.4f} m{b['dd_m']}/c{b['dd_nch']} pf={str(b['pfm'])[0]}")
    print()


if __name__ == "__main__":
    for q, t in [("무좀", "무좀"), ("여드름", "여드름"), ("아토피", "아토피")]:
        measure(q, t)
