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

from typing import TYPE_CHECKING

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter

if TYPE_CHECKING:
    from shared.models import Classification, ImageAnalysisResult

from ai import (
    classify_hospital,
    extract_services_and_doctors,
    find_related_hospitals,
    generate_description,
    ingest_hospital,
)
from ai.search.kb_store import build_ingest_metadata, build_signal_chunks


def _record_classification_change(
    db: DynamoAdapter,
    prev: "Classification | None",
    current: "Classification",
) -> None:
    """primary_focus 가 이전 분류와 다르면 ClassificationChange(HISTORY#) 를 적재한다.

    이전 분류가 없으면(최초 분류) 기록하지 않는다 — 변경이 아니라 신규이므로.
    재크롤·재분류 경로(index_pipeline)에서 호출되어 영역 ⑦ 변경 이력을 자동 생성한다.
    """
    if prev is None:
        return
    if prev.primary_focus == current.primary_focus:
        return

    from shared.models import ClassificationChange

    db.save_change_record(
        ClassificationChange(
            hospital_id=current.hospital_id,
            changed_at=current.classified_at,
            from_focus=prev.primary_focus,
            to_focus=current.primary_focus,
            reason="scheduled_recrawl",
            classifier_version=current.classifier_version,
        )
    )


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

    # 외부 시그널 로드 (적재된 것만 — 없으면 None, 자체 사이트만 분류)
    external = db.load_external_signals(hospital_id)

    # Vision 결과 로드 — DDB VISION#RESULTS 가 있으면(=시연 10개 demo) 합류.
    # 없으면 None (1만 베이스라인에서는 Vision 미실행). run_vision_demo 가 1회 적재한
    # 결과를 분류·extract·KB 청크가 공유해 analyze_images 중복 호출을 피한다.
    # DDB 에는 dict 로 저장되므로 ImageAnalysisResult 로 정규화해 AI 함수에 전달한다.
    vision_results_raw = db.get_entity(hospital_id, "VISION#RESULTS")
    vision_results: "list[ImageAnalysisResult] | None" = None
    if vision_results_raw:
        from shared.models import ImageAnalysisResult

        vision_results = [
            ImageAnalysisResult(**r) for r in (vision_results_raw.get("results") or [])
        ]

    # 재분류 비교용 — 이전 CLASSIFICATION 을 분류 저장 전에 로드
    prev_classification = db.load_classification(hospital_id)

    # 분류 — demo 면 LLM, 아니면 룰 단독(Bedrock 0회). 외부 후기·카카오 tags 까지 교차검증.
    # Vision 결과가 있으면 전달 → 분류기가 재분석하지 않고 재사용 (시연 10개).
    classification = classify_hospital(
        crawl_data,
        use_llm=demo,
        standard_specialty=hospital_meta.standard_specialty,
        vision_results=vision_results,
        **external,
    )
    db.save_classification(classification)

    # 분류 변경 자동 기록 — primary_focus 가 이전과 다르면 HISTORY# 적재 (영역 ⑦)
    _record_classification_change(db, prev_classification, classification)

    # 시연 10개만 — 진료항목·설명·관련병원 (LLM/Vision)
    if demo:
        # vision_results 가 있으면 extract_services_and_doctors 에도 전달
        services_and_doctors = extract_services_and_doctors(
            crawl_data=crawl_data,
            classification=classification,
            vision_results=vision_results or [],
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
    # 외부 시그널(카카오/네이버/구글) + Vision 결과(있으면) 함께 청크에 합류
    signal_chunks = build_signal_chunks(
        crawl_data=crawl_data,
        vision_results=vision_results,
        **external,
    )
    metadata = build_ingest_metadata(hospital_meta, classification)
    ingest_hospital(
        hospital_id,
        signal_chunks,
        metadata,
        trigger_ingestion=trigger_ingestion,
    )

    return {"status": "indexed", "hospital_id": hospital_id, "demo": demo}
