"""목록형 UX용 랭킹 품질 — NDCG@10·P@10 추가 측정 (focus_rank_eval 재사용).

P@1(claimer@1)은 '1등 하나'만 보는 잣대라 목록 브라우징 UX엔 부적합.
사용자가 위→아래 관련도 순 목록을 본다면 '상위가 관련도 순으로 정렬됐나'(NDCG)가 본질.
focus_rank_eval 의 load_focus_map 을 그대로 써서 같은 84토픽에 NDCG@10·P@5·P@10·MRR 측정.

실행:
  RANK_MODE=cosine    .venv/bin/python be/scripts/_ndcg_eval.py
  RANK_MODE=intensity .venv/bin/python be/scripts/_ndcg_eval.py
"""
from __future__ import annotations

import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from be.scripts.focus_rank_eval import (  # noqa: E402
    MAX_TERMS, MIN_HOSP, SIGUNGU, TOPK, WORKERS, RANK_MODE, load_focus_map,
)
from ai import retrieve_hospital  # noqa: E402
from shared.models import SearchQuery  # noqa: E402


def _dcg(rels: list[int]) -> float:
    return sum(r / math.log2(i + 1) for i, r in enumerate(rels, 1))


def eval_term(term: str, relevant: set[str]) -> dict | None:
    try:
        res = retrieve_hospital(SearchQuery(query_text=term, sigungu=SIGUNGU, limit=TOPK))
    except Exception:
        return None
    ids = [r.hospital_id for r in res]
    hits = [1 if h in relevant else 0 for h in ids]
    if not hits:
        return {"p1": 0, "p5": 0.0, "p10": 0.0, "mrr": 0.0, "ndcg": 0.0,
                "oracle_ndcg": 0.0, "oracle_p1": 0.0, "dead": 1.0}
    p1 = hits[0]
    p5 = sum(hits[:5]) / 5.0
    p10 = sum(hits[:10]) / 10.0
    mrr = next((1.0 / i for i, h in enumerate(hits, 1) if h), 0.0)
    ideal = _dcg(sorted(hits, reverse=True)[:10])
    ndcg = (_dcg(hits[:10]) / ideal) if ideal else 0.0
    any_hit = 1.0 if sum(hits[:10]) else 0.0
    # oracle = 회수된 top-10을 완벽히 재정렬했을 때(=리랭커 천장). 관련 1개라도 회수되면
    # NDCG·P@1 모두 1.0, 하나도 못 회수했으면(thin-signal=리콜 손실) 0.0.
    return {"p1": p1, "p5": p5, "p10": p10, "mrr": mrr, "ndcg": ndcg,
            "oracle_ndcg": any_hit, "oracle_p1": any_hit, "dead": 1.0 - any_hit}


def main() -> None:
    term_hosp, _ = load_focus_map()
    terms = [(tm, hs) for tm, hs in term_hosp.items()
             if len(hs) >= MIN_HOSP and tm and len(tm) >= 2]
    terms.sort(key=lambda x: -len(x[1]))
    terms = terms[:MAX_TERMS]
    print(f"RANK_MODE={RANK_MODE} | 토픽 {len(terms)}개 | top{TOPK} | 강남")

    rows = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for r in ex.map(lambda t: eval_term(t[0], t[1]), terms):
            if r is not None:
                rows.append(r)
    n = len(rows)
    keys = ("p1", "p5", "p10", "mrr", "ndcg", "oracle_ndcg", "oracle_p1", "dead")
    agg = {k: sum(r[k] for r in rows) / n for k in keys}
    n_dead = int(sum(r["dead"] for r in rows))
    live = [r for r in rows if r["dead"] == 0.0]
    ndcg_live = sum(r["ndcg"] for r in live) / len(live) if live else 0.0
    print(f"\n=== 매크로 (쿼리 {n}개) ===")
    print(f"  P@1         = {agg['p1']:.3f}")
    print(f"  P@5         = {agg['p5']:.3f}")
    print(f"  P@10        = {agg['p10']:.3f}")
    print(f"  MRR         = {agg['mrr']:.3f}")
    print(f"  NDCG@10     = {agg['ndcg']:.3f}   <- 현재 목록 정렬 품질")
    print(f"\n  --- 천장/바닥 분해 ---")
    print(f"  oracle NDCG = {agg['oracle_ndcg']:.3f}   <- 완벽한 리랭커 천장(회수된 것 완벽정렬)")
    print(f"  oracle P@1  = {agg['oracle_p1']:.3f}   <- 리랭커가 도달가능한 P@1 최대")
    print(f"  ① 리랭커 최대 여지 = {agg['oracle_ndcg'] - agg['ndcg']:+.3f} NDCG / {agg['oracle_p1'] - agg['p1']:+.3f} P@1")
    print(f"  ② 리콜에 갇힌 손실 = {1.0 - agg['oracle_ndcg']:.3f} (관련 0개 회수 토픽 {n_dead}/{n}개)")
    print(f"  회수성공 토픽({len(live)}개)의 현재 NDCG = {ndcg_live:.3f}   <- 이미 잘 정렬돼 있나")


if __name__ == "__main__":
    main()
