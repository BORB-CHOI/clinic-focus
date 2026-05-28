"""룰 기반 분류 배치 — 전체 병원 classify(use_llm=False) → DDB CLASSIFICATION 적재
+ 시그널 청크 KB ingest. LLM 0회 호출이라 전체 1만에 적용 가능 (트랙 A 베이스라인).

DESCRIPTION·진료항목 등 LLM/Vision 산출물(시연 10개)은 이 배치가 아니라
demo 파이프라인(run_index_pipeline(demo=True))에서 따로 만든다 — 검색 임베딩이
DESCRIPTION 이 아니라 시그널 청크로 구성되므로 배치에서 설명 생성이 불필요하다
(docs/plans/task-queue.md Phase C 결정).

병원 목록은 DDB META 항목을 순회한다. 크롤 본문은 S3 에서 로드.
배치는 trigger_ingestion=False 로 전부 적재한 뒤 마지막에 ingestion job 1회만 트리거.

실행: .venv/bin/python be/scripts/run_classification.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import boto3

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter


def main():
    db = DynamoAdapter()
    s3 = S3Adapter()

    print("=" * 60)
    print("룰 기반 분류 배치 (use_llm=False, Bedrock 0회)")
    print("=" * 60)

    try:
        from ai import classify_hospital, ingest_hospital
        from ai.search.kb_store import build_ingest_metadata, build_signal_chunks
    except ImportError as e:
        print(f"❌ AI 모듈 import 실패: {e}")
        return

    hospital_ids = list(db.iter_all_hospital_ids())
    print(f"  전체 병원: {len(hospital_ids)}개\n")

    success = 0
    skipped = 0
    failed = 0

    for i, hospital_id in enumerate(hospital_ids, 1):
        try:
            crawl_data = s3.load_crawl_data(hospital_id)
            hospital_meta = db.load_hospital_meta(hospital_id)
            if not crawl_data or not crawl_data.pages or not hospital_meta:
                skipped += 1
                continue

            # 외부 시그널 로드 (적재된 것만 — 없으면 None, 자체 사이트만 분류)
            external = db.load_external_signals(hospital_id)

            # 룰 분류 (LLM 0회) → DDB 저장. 외부 후기·카카오 tags 까지 4 시그널 교차검증.
            classification = classify_hospital(crawl_data, use_llm=False, **external)
            db.save_classification(classification)

            # 시그널 청크 KB ingest — 배치라 트리거는 마지막 1회만
            signal_chunks = build_signal_chunks(crawl_data=crawl_data, **external)
            metadata = build_ingest_metadata(hospital_meta, classification)
            ingest_hospital(hospital_id, signal_chunks, metadata, trigger_ingestion=False)

            success += 1
            print(f"  [{i}/{len(hospital_ids)}] ✅ {hospital_meta.name} — {classification.primary_focus} "
                  f"(신뢰도 {classification.confidence.score} {classification.confidence.level})")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(hospital_ids)}] ❌ {hospital_id} — {e}")

    # 모두 적재 후 KB ingestion job 1회 트리거
    if success > 0:
        print("\n[KB ingestion job 트리거]")
        agent = boto3.client("bedrock-agent", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        job = agent.start_ingestion_job(
            knowledgeBaseId=os.environ["KB_ID"],
            dataSourceId=os.environ["KB_DATA_SOURCE_ID"],
        )
        print(f"  job_id={job['ingestionJob']['ingestionJobId']} status={job['ingestionJob']['status']}")

    print("\n" + "=" * 60)
    print(f"룰 분류 배치 완료 — ✅ {success}  ⏭️ {skipped}  ❌ {failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
