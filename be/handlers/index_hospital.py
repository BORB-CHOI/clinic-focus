"""병원 인덱싱 파이프라인 — AI 분류 + (데모) 설명 + DDB 적재 + KB 시그널 청크 ingest.

두 모드:
  demo=False (기본·룰 베이스라인) — classify(use_llm=False, LLM 0회) → 분류 저장
      → 시그널 청크 KB ingest. 전체 1만에 적용 가능, 비용 0.
  demo=True (시연 10개) — classify(use_llm=True) + 진료항목·설명·관련병원(LLM/Vision)
      추가 생성·저장. DESCRIPTION 은 상세페이지 표시용이며 임베딩에는 들어가지 않는다.

검색 임베딩은 DESCRIPTION 이 아니라 시그널별 청크(자칭/블로그/후기)로 구성한다
(docs/plans/task-queue.md Phase C 결정).
"""

from __future__ import annotations

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter

from ai import (
    classify_hospital,
    extract_services_and_doctors,
    find_related_hospitals,
    generate_description,
    ingest_hospital,
)
from ai.search.kb_store import build_ingest_metadata, build_signal_chunks


def run_index_pipeline(
    hospital_id: str,
    *,
    demo: bool = False,
    trigger_ingestion: bool = True,
) -> dict:
    """S3 CrawlData → 분류 → DDB 적재 → KB 시그널 청크 ingest.

    Args:
        hospital_id: 대상 병원.
        demo: True 면 LLM/Vision 까지 (시연 10개). False 면 룰 단독 베이스라인.
        trigger_ingestion: 단건 호출은 True(즉시 ingestion job). 배치는 False 로
            모두 적재 후 마지막 1회만 트리거.
    """
    db = DynamoAdapter()
    s3 = S3Adapter()

    crawl_data = s3.load_crawl_data(hospital_id)
    if not crawl_data:
        return {"status": "error", "reason": "crawl_data_not_found", "hospital_id": hospital_id}

    hospital_meta = db.load_hospital_meta(hospital_id)
    if not hospital_meta:
        return {"status": "error", "reason": "hospital_meta_not_found", "hospital_id": hospital_id}

    # 분류 — demo 면 LLM, 아니면 룰 단독(Bedrock 0회)
    classification = classify_hospital(crawl_data, use_llm=demo)
    db.save_classification(classification)

    # 시연 10개만 — 진료항목·설명·관련병원 (LLM/Vision)
    if demo:
        services_and_doctors = extract_services_and_doctors(
            crawl_data=crawl_data,
            classification=classification,
            vision_results=[],
        )
        description = generate_description(
            classification=classification,
            detailed_signals=classification.detailed_signals,
            hospital_meta=hospital_meta,
        )
        related = find_related_hospitals(
            hospital_id=hospital_id,
            location=hospital_meta.location,
            primary_focus=classification.primary_focus,
            excluded_services=services_and_doctors.excluded_services,
        )
        db.save_description(description)
        db.save_services_and_doctors(hospital_id, services_and_doctors)
        db.save_related_hospitals(hospital_id, related)

    # KB 시그널 청크 ingest — 검색 임베딩 (DESCRIPTION 미포함)
    # TODO: 카카오/네이버 시그널 DDB entity 적재되면 build_signal_chunks 에 함께 전달
    signal_chunks = build_signal_chunks(crawl_data=crawl_data)
    metadata = build_ingest_metadata(hospital_meta, classification)
    ingest_hospital(
        hospital_id,
        signal_chunks,
        metadata,
        trigger_ingestion=trigger_ingestion,
    )

    return {"status": "indexed", "hospital_id": hospital_id, "demo": demo}
