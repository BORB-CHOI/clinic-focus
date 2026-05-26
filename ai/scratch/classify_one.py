"""1개 병원으로 classify_hospital + generate_description 도는지 검증.

가장 큰 CrawlData JSON 을 골라서 ai.pipeline 두 함수를 차례로 호출.
결과는 stdout 에 print — 의도는 '눈으로 확인'.

실행:
    .venv/bin/python ai/scratch/classify_one.py
"""

from __future__ import annotations

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from be.scripts._utils import load_env  # noqa: E402

load_env()

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402
from be.adapters.s3_adapter import S3Adapter  # noqa: E402

from ai import classify_hospital, extract_services_and_doctors, generate_description  # noqa: E402


# 105KB 짜리 — 강남구 9페이지 30이미지 가장 풍부했던 케이스
TARGET_FILE = "JDQ4MTg4MSM1MSMkMSMkMCMkOTkkMzgxMzUxIzMxIyQxIyQzIyQ2MiQyNjE0ODEjNzEjJDEjJDgjJDgz.json"


def main() -> None:
    hospital_id = TARGET_FILE.removesuffix(".json")

    s3 = S3Adapter()
    db = DynamoAdapter()

    print("=" * 60)
    print(f"AI 파이프라인 검증 — 1개 병원 (hospital_id={hospital_id[:30]}...)")
    print("=" * 60)

    print("\n[1/4] CrawlData 로드")
    crawl_data = s3.load_crawl_data(hospital_id)
    if not crawl_data:
        print(f"  ❌ CrawlData 없음: {hospital_id}")
        return
    print(f"  ✅ pages={len(crawl_data.pages)}, images={len(crawl_data.images)}, url={crawl_data.website_url}")

    print("\n[2/4] HospitalMeta 로드")
    meta = db.load_hospital_meta(hospital_id)
    if not meta:
        print(f"  ❌ HospitalMeta 없음")
        return
    print(f"  ✅ name={meta.name}, sigungu={meta.location.sigungu}")

    print("\n[3/4] classify_hospital — 4 시그널 교차 검증")
    classification = classify_hospital(crawl_data)
    print(f"  ✅ standard_specialty={classification.standard_specialty}")
    print(f"     primary_focus={classification.primary_focus}")
    print(f"     confidence.score={classification.confidence.score}")
    print(f"     signals={classification.confidence.signals}")

    print("\n[4/4] generate_description — AI 통합 설명")
    description = generate_description(
        classification=classification,
        detailed_signals=classification.detailed_signals,
        hospital_meta=meta,
    )
    print(f"  ✅ paragraphs:")
    for i, p in enumerate(description.paragraphs, 1):
        print(f"  ── [{i}] {p.text[:200]}{'...' if len(p.text) > 200 else ''}")

    print("\n" + "=" * 60)
    print("완료 — 분류·설명 e2e 통과")
    print("=" * 60)


if __name__ == "__main__":
    main()
