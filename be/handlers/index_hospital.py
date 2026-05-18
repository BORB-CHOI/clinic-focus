"""병원 인덱싱 Lambda — AI 분류 + 설명 생성 + DB 적재 + 벡터 인덱싱."""

from __future__ import annotations

import json
import os

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter
from shared.models import CrawlData, HospitalMeta

# AI 모듈은 같은 패키지에서 import (단일 Lambda 배포)
from ai import (
    classify_hospital,
    extract_services_and_doctors,
    find_related_hospitals,
    generate_description,
    index_hospital,
)


def handler(event, context):
    """
    SQS 트리거 Lambda.
    S3에서 CrawlData 로드 → AI 분류 → 설명 생성 → DynamoDB 적재 → 벡터 인덱싱.
    """
    db = DynamoAdapter()
    s3 = S3Adapter()

    record = json.loads(event["Records"][0]["body"])
    hospital_id = record["hospital_id"]

    # 1. 크롤링 데이터 로드
    crawl_data = s3.load_crawl_data(hospital_id)
    if not crawl_data:
        return {"status": "error", "reason": "crawl_data_not_found", "hospital_id": hospital_id}

    hospital_meta = db.load_hospital_meta(hospital_id)
    if not hospital_meta:
        return {"status": "error", "reason": "hospital_meta_not_found", "hospital_id": hospital_id}

    # 2. AI 분류
    classification = classify_hospital(crawl_data)

    # 3. 진료 항목·의료기기·의료진 추출
    services_and_doctors = extract_services_and_doctors(
        crawl_data=crawl_data,
        classification=classification,
        vision_results=[],  # Phase 1에서는 Vision 결과 별도 처리
    )

    # 4. AI 통합 상세 설명 생성
    description = generate_description(
        classification=classification,
        detailed_signals=classification.detailed_signals,
        hospital_meta=hospital_meta,
    )

    # 5. 관련 병원 추천
    related = find_related_hospitals(
        hospital_id=hospital_id,
        location=hospital_meta.location,
        primary_focus=classification.primary_focus,
        excluded_services=services_and_doctors.excluded_services,
    )

    # 6. DynamoDB 적재
    db.save_classification(classification)
    db.save_description(description)
    db.save_services_and_doctors(hospital_id, services_and_doctors)
    db.save_related_hospitals(hospital_id, related)

    # 7. S3 Vectors 인덱싱
    embedding_text = "\n".join(p.text for p in description.paragraphs)
    index_hospital(hospital_id, classification, embedding_text)

    return {"status": "indexed", "hospital_id": hospital_id}
