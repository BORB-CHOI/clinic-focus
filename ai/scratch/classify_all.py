"""크롤링 성공한 14개 병원 전체에 대해 classify + describe + DDB 저장.

실행:
    .venv/bin/python ai/scratch/classify_all.py

각 단계 진행상황 stdout 출력. 실패한 병원은 스킵.
"""

from __future__ import annotations

import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from be.scripts._utils import load_env  # noqa: E402

load_env()

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402
from be.adapters.s3_adapter import S3Adapter  # noqa: E402

from ai import classify_hospital, generate_description  # noqa: E402


def main() -> None:
    crawl_dir = os.environ.get(
        "CRAWL_DATA_DIR",
        os.path.join(PROJECT_ROOT, "data", "crawl"),
    )
    files = sorted([f for f in os.listdir(crawl_dir) if f.endswith(".json")])

    print("=" * 60)
    print(f"AI 파이프라인 14개 일괄 — classify + describe + DDB save")
    print("=" * 60)
    print(f"대상: {len(files)}개\n")

    s3 = S3Adapter()
    db = DynamoAdapter()

    results = {"success": 0, "classify_fail": 0, "describe_fail": 0}
    start = time.time()

    for i, fname in enumerate(files, 1):
        hospital_id = fname.removesuffix(".json")
        short_id = hospital_id[:30] + "..."

        crawl_data = s3.load_crawl_data(hospital_id)
        meta = db.load_hospital_meta(hospital_id)
        if not crawl_data or not meta:
            print(f"[{i:2d}/{len(files)}] ❌ 데이터 누락 — {short_id}")
            continue

        print(f"[{i:2d}/{len(files)}] {meta.name} ({meta.location.sigungu})")

        try:
            classification = classify_hospital(crawl_data)
            db.save_classification(classification)
            print(
                f"           ✅ classify: {classification.standard_specialty}"
                f" → {classification.primary_focus}"
                f" (conf={classification.confidence.score})"
            )
        except Exception as e:
            results["classify_fail"] += 1
            print(f"           ❌ classify 실패: {str(e)[:120]}")
            continue

        try:
            description = generate_description(
                classification=classification,
                detailed_signals=classification.detailed_signals,
                hospital_meta=meta,
            )
            db.save_description(description)
            print(f"           ✅ describe: {len(description.paragraphs)}단락 생성·저장")
            results["success"] += 1
        except Exception as e:
            results["describe_fail"] += 1
            print(f"           ❌ describe 실패: {str(e)[:120]}")

    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"완료 — {elapsed:.1f}초 소요")
    print(f"  ✅ 전체 성공 (분류+설명): {results['success']}/{len(files)}")
    print(f"  ❌ 분류 실패: {results['classify_fail']}")
    print(f"  ❌ 설명 실패: {results['describe_fail']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
