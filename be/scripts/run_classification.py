"""룰 기반 분류 배치 — 전체 병원 classify(use_llm=False) → DDB CLASSIFICATION 적재
+ 시그널 청크 KB ingest. LLM 0회 호출이라 전체 1만에 적용 가능 (트랙 A 베이스라인).

DESCRIPTION·진료항목 등 LLM/Vision 산출물(시연 약 500개)은 이 배치가 아니라
demo 파이프라인(run_index_pipeline(demo=True))에서 따로 만든다 — 검색 임베딩이
DESCRIPTION 이 아니라 시그널 청크로 구성되므로 배치에서 설명 생성이 불필요하다
(docs/plans/task-queue.md Phase C 결정).

병원 목록은 DDB META 항목을 순회한다. 크롤 본문은 S3 에서 로드.
배치는 trigger_ingestion=False 로 전부 적재한 뒤 마지막에 ingestion job 1회만 트리거.

실행: .venv/bin/python be/scripts/run_classification.py
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import boto3

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter
from be.core.crawler import site_mentions_hospital
from shared.models import CrawlData


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="룰 기반 분류 배치")
    parser.add_argument(
        "--sigungu", default=None,
        help="특정 시군구만 분류 (예: 강남구). 미지정 시 전체 META.",
    )
    parser.add_argument(
        "--name-contains", default=None, dest="name_contains",
        help="병원명에 이 문자열이 포함된 곳만 재분류 (예: 여성). 타깃 재분류·재인제스트용.",
    )
    args = parser.parse_args(argv)

    db = DynamoAdapter()
    s3 = S3Adapter()

    print("=" * 60)
    print("룰 기반 분류 배치 (use_llm=False, Bedrock 0회)")
    print("=" * 60)

    try:
        from ai import classify_hospital, ingest_hospital
        from ai.core.exceptions import InsufficientDataError
        from ai.search.kb_store import build_ingest_metadata, build_signal_chunks
    except ImportError as e:
        print(f"❌ AI 모듈 import 실패: {e}")
        return

    # 대상 결정 — 시군구 지정 시 그 구만, 아니면 전체 META. --name-contains 로 이름 필터.
    if args.sigungu:
        metas = db.list_hospitals_by_sigungu(args.sigungu)
        if args.name_contains:
            metas = [m for m in metas if args.name_contains in (m.name or "")]
        hospital_ids = [m.hospital_id for m in metas]
    else:
        hospital_ids = list(db.iter_all_hospital_ids())
        if args.name_contains:
            hospital_ids = [
                hid for hid in hospital_ids
                if (m := db.load_hospital_meta(hid)) and args.name_contains in (m.name or "")
            ]
    scope = (args.sigungu or "전체") + (f" / 이름~'{args.name_contains}'" if args.name_contains else "")
    print(f"  대상: {scope} {len(hospital_ids)}개\n")

    success = 0
    skipped = 0
    failed = 0
    name_mismatch = 0  # URL 오매칭 의심으로 자칭 시그널 제외한 수

    for i, hospital_id in enumerate(hospital_ids, 1):
        try:
            hospital_meta = db.load_hospital_meta(hospital_id)
            if not hospital_meta:
                skipped += 1  # META 없으면 분류 불가
                continue

            # 자체사이트 크롤본문 — 없으면 빈 CrawlData 로 진행(웹사이트 필수 아님).
            # 외부 시그널만으로도 분류하고, 그마저 없으면 score 0 '정보 부족'(후순위)로
            # 저장해 검색에 '뜨긴 뜨게' 한다 (사라지면 의료법상 차별 노출 소지).
            crawl_data = s3.load_crawl_data(hospital_id)
            _empty_site = CrawlData(
                hospital_id=hospital_id,
                website_url=(hospital_meta.contact.website_url or "")
                if hospital_meta.contact else "",
                pages=[],
                images=[],
            )
            if crawl_data is None or not crawl_data.pages:
                crawl_data = _empty_site
            elif not site_mentions_hospital(hospital_meta.name, crawl_data):
                # URL 오매칭 방어: 본문에 병원명이 전혀 없으면 엉뚱한 사이트일 개연성 →
                # 자칭 시그널 제외(빈 사이트로). 외부 시그널만으로 분류(틀린 자칭 < 빈 자칭).
                name_mismatch += 1
                crawl_data = _empty_site

            # 외부 시그널 로드 (적재된 것만 — 없으면 None)
            external = db.load_external_signals(hospital_id)

            # 룰 분류 (LLM 0회) → DDB 저장. HIRA 진료과(META) 권위 사용 + taxonomy 태깅.
            classification = classify_hospital(
                crawl_data,
                use_llm=False,
                standard_specialty=hospital_meta.standard_specialty,
                **external,
            )
            db.save_classification(classification)

            # 시그널 청크 KB ingest — 청크가 있을 때만(자칭·외부 무엇이든 있어야 임베딩 의미).
            # 시그널 0 인 placeholder 병원은 KB 미적재(검색은 시군구 GSI 로 노출).
            signal_chunks = build_signal_chunks(crawl_data=crawl_data, **external)
            if signal_chunks:
                metadata = build_ingest_metadata(hospital_meta, classification)
                # prune_absent: 자칭이 URL 오매칭으로 비워졌을 때 옛 self_claim 청크(stale 메타)가
                # S3 에 잔존해 검색을 오염시키지 않도록, 이번에 안 만든 시그널의 옛 파일을 삭제.
                # build_signal_chunks 가 전체 시그널을 한 번에 채워 넘기므로 안전.
                ingest_hospital(
                    hospital_id, signal_chunks, metadata,
                    trigger_ingestion=False, prune_absent=True,
                )

            success += 1
            print(f"  [{i}/{len(hospital_ids)}] ✅ {hospital_meta.name} — {classification.primary_focus} "
                  f"(신뢰도 {classification.confidence.score} {classification.confidence.level})")
        except InsufficientDataError:
            # 자체사이트·외부 시그널 모두 없음 → 분류 스킵. META 는 남아 카테고리 검색엔 노출.
            skipped += 1
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
    print(f"  (URL 오매칭 의심으로 자칭 제외: {name_mismatch}개)")
    print("=" * 60)


if __name__ == "__main__":
    main()
