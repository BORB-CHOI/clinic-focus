"""인자로 받은 자연어 한 줄을 KB 에 검색해 결과 출력.

사용:
    .venv/bin/python ai/scratch/search_one.py "여드름 잘 보는 피부과"
"""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from be.scripts._utils import load_env  # noqa: E402

load_env()

import boto3  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("사용: python ai/scratch/search_one.py <검색어>")
        sys.exit(1)

    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("검색어가 비어있음.")
        sys.exit(1)

    kb_id = os.environ["KB_ID"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-agent-runtime", region_name=region)

    print(f"\n[쿼리] {query!r}")
    print("-" * 70)

    resp = client.retrieve(
        knowledgeBaseId=kb_id,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {
                "numberOfResults": 5,
                "filter": {"equals": {"key": "team_id", "value": "clinic-focus"}},
            }
        },
    )

    results = resp.get("retrievalResults", [])
    if not results:
        print("  (결과 없음)")
        return

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
                "snippet": r.get("content", {}).get("text", ""),
            }

    sorted_results = sorted(by_hospital.values(), key=lambda x: -x["score"])
    for i, r in enumerate(sorted_results, 1):
        focus_str = ", ".join(r["focus"]) if isinstance(r["focus"], list) else str(r["focus"])
        print(f"\n[{i}] {r['name']} ({r['specialty']}) — score {r['score']:.3f}")
        if focus_str:
            print(f"     주력: {focus_str}")
        snippet = r["snippet"].replace("\n\n", " // ").strip()
        print(f"     발췌: {snippet[:280]}{'...' if len(snippet) > 280 else ''}")

    print("\n" + "-" * 70)
    print(f"총 {len(sorted_results)}개 병원")


if __name__ == "__main__":
    main()
