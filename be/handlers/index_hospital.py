"""병원 인덱싱 파이프라인 — AI 분류 + 설명 생성 + DB 적재 + 벡터 인덱싱."""

from __future__ import annotations

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter

from ai import (
    classify_hospital,
    extract_services_and_doctors,
    find_related_hospitals,
    generate_description,
    index_hospital,
)


def run_index_pipeline(hospital_id: str) -> dict:
    """
    S3에서 CrawlData 로드 → AI 분류 → 설명 생성 → DynamoDB 적재 → 벡터 인덱싱.
    EC2 스크립트나 큐 컨슈머에서 직접 호출.
    """
    db = DynamoAdapter()
    s3 = S3Adapter()

    crawl_data = s3.load_crawl_data(hospital_id)
    if not crawl_data:
        return {"status": "error", "reason": "crawl_data_not_found", "hospital_id": hospital_id}

    hospital_meta = db.load_hospital_meta(hospital_id)
    if not hospital_meta:
        return {"status": "error", "reason": "hospital_meta_not_found", "hospital_id": hospital_id}

    # AI 분류
    classification = classify_hospital(crawl_data)

    # 진료 항목·의료기기·의료진 추출
    services_and_doctors = extract_services_and_doctors(
        crawl_data=crawl_data,
        classification=classification,
        vision_results=[],
    )

    # AI 통합 상세 설명 생성
    description = generate_description(
        classification=classification,
        detailed_signals=classification.detailed_signals,
        hospital_meta=hospital_meta,
    )

    # 관련 병원 추천
    related = find_related_hospitals(
        hospital_id=hospital_id,
        location=hospital_meta.location,
        primary_focus=classification.primary_focus,
        excluded_services=services_and_doctors.excluded_services,
    )

    # DynamoDB 적재
    db.save_classification(classification)
    db.save_description(description)
    db.save_services_and_doctors(hospital_id, services_and_doctors)
    db.save_related_hospitals(hospital_id, related)

    # S3 Vectors 인덱싱 (위치 파라미터 포함)
    embedding_text = "\n".join(p.text for p in description.paragraphs)
    index_hospital(
        hospital_id=hospital_id,
        classification=classification,
        description_text=embedding_text,
        sido=hospital_meta.location.sido,
        sigungu=hospital_meta.location.sigungu,
        lat=hospital_meta.location.lat,
        lng=hospital_meta.location.lng,
    )

    return {"status": "indexed", "hospital_id": hospital_id}
