"""시연 검색어 프리워밍 — 리랭커 캐시를 미리 데워 시연 때 0초 응답.

리랭커(RERANK_MODE=llm)는 검색당 Nova Lite 1회 호출이라 첫 검색에 ~1~2초 걸린다.
리랭커는 결과를 (query, model, 후보집합) 키로 캐시하므로, **시연 직전에 보여줄 검색어를
한 번씩 돌려두면** 실제 시연 땐 캐시 히트로 즉시 응답한다(서버 프로세스가 살아있는 한 유지).

캐시는 서버 프로세스 메모리에 있으므로 **반드시 실행 중인 BE 서버의 /api/search 를 친다**
(별도 프로세스에서 retrieve_hospital 직접 호출하면 그 프로세스 캐시만 데워져 무의미).

사용:
    .venv/bin/python be/scripts/prewarm_search.py
    .venv/bin/python be/scripts/prewarm_search.py --base-url http://localhost:8000 임플란트 탈모
"""
from __future__ import annotations

import argparse
import sys
import time

import httpx

# 시연에서 보여줄 자연어 검색어(편집해서 쓰면 됨). 진료과 분포를 두루 커버.
DEFAULT_QUERIES = [
    "임플란트", "라식 라섹", "모발이식 탈모", "코골이 수면무호흡", "보톡스 필러",
    "무좀", "사마귀 냉동치료", "어린이 예방접종", "편도염", "허리 디스크",
    "여드름 흉터", "갑상선 결절", "당뇨 관리", "우울증 상담", "독감 검사",
]
SIGUNGU = "강남구"  # 강남 PoC 범위


def main() -> int:
    ap = argparse.ArgumentParser(description="리랭커 캐시 프리워밍")
    ap.add_argument("queries", nargs="*", help="검색어(생략 시 DEFAULT_QUERIES)")
    ap.add_argument("--base-url", default="http://localhost:8000", help="실행 중인 BE 서버")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    queries = args.queries or DEFAULT_QUERIES
    print(f"프리워밍 {len(queries)}개 → {args.base_url}/api/search (sigungu={SIGUNGU})")
    ok = 0
    with httpx.Client(timeout=30.0) as client:
        for q in queries:
            t0 = time.perf_counter()
            try:
                r = client.get(f"{args.base_url}/api/search", params={
                    "q": q, "sigungu": SIGUNGU, "sort": "relevance", "limit": args.limit,
                })
                r.raise_for_status()
                n = len(r.json().get("data", []))
                dt = (time.perf_counter() - t0) * 1000
                print(f"  ✓ {q:18s} {n:2d}건 {dt:6.0f}ms")
                ok += 1
            except Exception as e:  # noqa: BLE001 — 워밍 실패는 치명 아님, 계속
                print(f"  ✗ {q:18s} 실패: {e}")
    print(f"완료 {ok}/{len(queries)}. 이제 같은 검색어는 캐시 히트로 즉시 응답(서버 유지 시).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
