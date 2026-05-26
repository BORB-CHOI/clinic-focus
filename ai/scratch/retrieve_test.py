"""KB Retrieve API 로 자연어 검색 결과 확인 — 14개 ingest 후 즉시 검증용.

쿼리 4개로 실측:
  - "여드름 미용 시술" → 피부과
  - "비염 코골이" → 이비인후과
  - "백내장 라식" → 안과
  - "강남구 피부과 보톡스"

각 쿼리마다 KB가 매칭한 청크의 metadata.hospital_id + similarity score + 본문 발췌 표시.
LLM 호출 0건 (KB가 내부에서 Titan v2 임베딩 1회 + 벡터 검색).

실행:
    .venv/bin/python ai/scratch/retrieve_test.py
"""

from __future__ import annotations

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from be.scripts._utils import load_env  # noqa: E402

load_env()

import boto3  # noqa: E402

QUERIES = [
    "여드름 잘 보는 피부과",
    "코골이 비염 수술",
    "백내장 라식 수술",
    "강남 보톡스 필러",
]


def main() -> None:
    kb_id = os.environ["KB_ID"]
    region = os.environ.get("AWS_REGION", "us-east-1")

    print("=" * 60)
    print(f"KB Retrieve 자연어 검색 테스트 (KB_ID={kb_id}, region={region})")
    print("=" * 60)

    client = boto3.client("bedrock-agent-runtime", region_name=region)

    for q in QUERIES:
        print(f"\n[쿼리] {q!r}")
        print("-" * 60)

        resp = client.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": q},
            retrievalConfiguration={
                "vectorSearchConfiguration": {
                    "numberOfResults": 5,
                    "filter": {
                        "equals": {"key": "team_id", "value": "clinic-focus"}
                    },
                }
            },
        )

        results = resp.get("retrievalResults", [])
        if not results:
            print("  (결과 없음)")
            continue

        # hospital_id 별 최고 점수만
        by_hospital: dict[str, dict] = {}
        for r in results:
            md = r.get("metadata", {})
            hid = md.get("hospital_id", "<?>")
            score = r.get("score", 0.0)
            if hid not in by_hospital or score > by_hospital[hid]["score"]:
                by_hospital[hid] = {
                    "score": score,
                    "name": md.get("name", "<?>"),
                    "specialty": md.get("standard_specialty", "<?>"),
                    "focus": md.get("primary_focus", []),
                    "snippet": r.get("content", {}).get("text", "")[:180],
                }

        # 점수순 정렬
        sorted_results = sorted(by_hospital.values(), key=lambda x: -x["score"])
        for i, r in enumerate(sorted_results, 1):
            focus_str = ", ".join(r["focus"]) if isinstance(r["focus"], list) else str(r["focus"])
            print(f"  [{i}] {r['name']} ({r['specialty']}) — score {r['score']:.3f}")
            print(f"      주력: {focus_str}")
            print(f"      발췌: {r['snippet'][:160]}...")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
