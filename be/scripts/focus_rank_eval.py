"""대규모 focus-recall eval — '주력 토픽을 검색하면 그 토픽을 주력으로 주장하는
병원이 상위에 오나'를 강남 primary_focus 용어 전수(수백 개)로 집계한다.

배경: 검색 랭킹을 코사인 1개로만 하면 '많이 언급/주력으로 주장'이 반영 안 됨
(유사도는 의미 근접도이지 주력이 아님). 이 eval 은 그 일반 효과를 한두 예가 아니라
강남에서 실제로 쓰이는 모든 주력 토픽에 대해 측정한다.

방법:
- 강남 분류의 primary_focus 를 모아 ≥MIN_HOSP 병원이 주장하는 토픽 T 들을 쿼리로 사용.
- 각 T 에 대해 retrieve_hospital(T) top-K. relevant = primary_focus 에 T 를 가진 병원.
- P@1·P@5·MRR·claimer@1 매크로 평균.
- RANK_MODE=cosine(옛 코사인-only) vs intensity(주력강도) 를 env 로 토글해 A/B.

실행:
  RANK_MODE=intensity .venv/bin/python be/scripts/focus_rank_eval.py
  RANK_MODE=cosine    .venv/bin/python be/scripts/focus_rank_eval.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import boto3  # noqa: E402
from boto3.dynamodb.conditions import Attr  # noqa: E402

from ai import retrieve_hospital  # noqa: E402
from shared.models import SearchQuery  # noqa: E402

SIGUNGU = os.environ.get("EVAL_SIGUNGU", "강남구")
MIN_HOSP = int(os.environ.get("EVAL_MIN_HOSP", "5"))   # 이 수 이상 병원이 주장하는 토픽만(의미있는 쿼리)
MAX_TERMS = int(os.environ.get("EVAL_MAX_TERMS", "400"))
TOPK = int(os.environ.get("EVAL_TOPK", "10"))
WORKERS = int(os.environ.get("EVAL_WORKERS", "8"))
RANK_MODE = os.environ.get("RANK_MODE", "intensity")

TABLE = os.environ.get("DYNAMO_TABLE", "kmuproj-10-clinic-Main")


def _norm(s: str) -> str:
    return str(s).strip().strip('"').strip()


def load_focus_map() -> tuple[dict[str, set[str]], dict[str, str]]:
    """강남 분류에서 (focus_term -> 그 토픽을 주장하는 hospital_id 집합), (hid -> name) 반환."""
    t = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")).Table(TABLE)

    # 강남 hospital_id + name (META)
    gangnam: dict[str, str] = {}
    kw = {"FilterExpression": Attr("entity").eq("META") & Attr("sigungu").eq(SIGUNGU),
          "ProjectionExpression": "hospital_id, #n", "ExpressionAttributeNames": {"#n": "name"}}
    while True:
        r = t.scan(**kw)
        for it in r["Items"]:
            gangnam[it["hospital_id"]] = it.get("name", "")
        if "LastEvaluatedKey" in r:
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
        else:
            break

    # CLASSIFICATION.primary_focus (강남만)
    term_hosp: dict[str, set[str]] = defaultdict(set)
    kw = {"FilterExpression": Attr("entity").eq("CLASSIFICATION"),
          "ProjectionExpression": "hospital_id, primary_focus"}
    while True:
        r = t.scan(**kw)
        for it in r["Items"]:
            hid = it["hospital_id"]
            if hid not in gangnam:
                continue
            for f in (it.get("primary_focus") or []):
                term_hosp[_norm(f)].add(hid)
        if "LastEvaluatedKey" in r:
            kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
        else:
            break
    return term_hosp, gangnam


def eval_term(term: str, relevant: set[str]) -> dict:
    """term 쿼리 → top-K. P@1·P@5·MRR·claimer@1 계산. relevant = pf 에 term 가진 병원."""
    try:
        res = retrieve_hospital(SearchQuery(query_text=term, sigungu=SIGUNGU, limit=TOPK))
    except Exception:
        return {"ok": False}
    ids = [r.hospital_id for r in res]
    hits = [1 if h in relevant else 0 for h in ids]
    p1 = hits[0] if hits else 0
    p5 = sum(hits[:5]) / 5.0
    mrr = 0.0
    for i, h in enumerate(hits, 1):
        if h:
            mrr = 1.0 / i
            break
    return {"ok": True, "p1": p1, "p5": p5, "mrr": mrr, "n_ret": len(ids),
            "n_rel": len(relevant), "top": ids[0] if ids else None}


def main():
    term_hosp, _ = load_focus_map()
    terms = [(tm, hs) for tm, hs in term_hosp.items()
             if len(hs) >= MIN_HOSP and tm and len(tm) >= 2]
    terms.sort(key=lambda x: -len(x[1]))
    terms = terms[:MAX_TERMS]
    print(f"RANK_MODE={RANK_MODE} | 토픽 {len(terms)}개 (≥{MIN_HOSP}병원 주장) | top{TOPK} | 강남")

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(eval_term, tm, hs): tm for tm, hs in terms}
        for f in futs:
            r = f.result()
            if r.get("ok"):
                r["term"] = futs[f]
                results.append(r)

    n = len(results)
    if not n:
        print("결과 없음"); return
    P1 = sum(r["p1"] for r in results) / n
    P5 = sum(r["p5"] for r in results) / n
    MRR = sum(r["mrr"] for r in results) / n
    print(f"\n=== 매크로 (쿼리 {n}개) ===")
    print(f"  P@1(claimer@1) = {P1:.3f}")
    print(f"  P@5            = {P5:.3f}")
    print(f"  MRR            = {MRR:.3f}")
    # 약한 토픽 일부 노출
    weak = sorted(results, key=lambda r: (r["p5"], r["mrr"]))[:12]
    print("\n  약한 토픽(P@5 낮은 순):")
    for r in weak:
        print(f"    {r['p5']:.1f} {r['mrr']:.2f}  {r['term']} (주장 {r['n_rel']}곳)")


if __name__ == "__main__":
    main()
