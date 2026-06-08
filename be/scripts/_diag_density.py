"""무좀 언급을 '비율(density)'과 '중복제거' 기준으로 재측정.

현재 랭킹의 mentions = 절대빈도(보일러플레이트 반복 포함).
- raw_mentions:    현재 방식 (모든 매칭 청크의 text.count 합)
- distinct_chunks: 청크 본문 dedup 후 '무좀 포함' 고유 청크 수
- uniq_mentions:   dedup 후 무좀 카운트 합
- total_chars:     매칭 청크 총 길이
- density‰:        raw_mentions / total_chars * 1000  (비율적 강조도)
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


def measure(query_text: str, term: str):
    p = process_query(query_text)
    kb_id = os.environ["KB_ID"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-agent-runtime", region_name=region)
    kb_filter = kb_store._build_kb_filter(
        specialty=[p.inferred_specialty, "기타"] if p.inferred_specialty else None
    )
    raw = kb_store._kb_retrieve(client, kb_id, p.embedding_text, kb_filter, 100)
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
            "max_score": 0.0, "raw_mentions": 0, "n_chunks": 0,
            "total_chars": 0, "seen_norm": set(), "uniq_mentions": 0, "distinct_chunks": 0,
        })
        g["max_score"] = max(g["max_score"], score)
        g["n_chunks"] += 1
        c = text.count(term)
        g["raw_mentions"] += c
        g["total_chars"] += len(text)
        # 보일러플레이트 dedup: 공백 제거한 본문 첫 120자를 시그니처로 near-dup 판정
        sig = "".join(text.split())[:120]
        if c > 0 and sig not in g["seen_norm"]:
            g["seen_norm"].add(sig)
            g["distinct_chunks"] += 1
            g["uniq_mentions"] += c

    rows = [g for g in agg.values() if g["max_score"] >= min_score]
    print("=" * 110)
    print(f"QUERY {query_text!r}  term={term!r}   (min-sim 통과 {len(rows)}개)")
    print("=" * 110)
    print(f"{'cos':>6} {'rawM':>5} {'uniqM':>5} {'distC':>5} {'nCh':>4} {'chars':>6} {'dens‰':>6}  name (sp)")
    for g in sorted(rows, key=lambda x: -x["raw_mentions"])[:14]:
        dens = g["raw_mentions"] / g["total_chars"] * 1000 if g["total_chars"] else 0
        print(f"{g['max_score']:.4f} {g['raw_mentions']:>5} {g['uniq_mentions']:>5} "
              f"{g['distinct_chunks']:>5} {g['n_chunks']:>4} {g['total_chars']:>6} {dens:>6.2f}  "
              f"{g['name']} ({g['sp']})")
    print()


if __name__ == "__main__":
    measure("무좀", "무좀")
    measure("여드름", "여드름")
