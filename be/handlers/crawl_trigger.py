"""크롤링 시작 트리거 — 심평원에서 병원 목록 가져와서 SQS에 넣기."""

from __future__ import annotations

import json
import os

from be.adapters.hira_adapter import HiraAdapter
from be.adapters.sqs_adapter import SQSAdapter
from be.adapters.dynamo_adapter import DynamoAdapter

CRAWL_QUEUE = os.environ.get("CRAWL_QUEUE_NAME", "ClinicFocusCrawlQueue")
# 성북구 시군구 코드
DEFAULT_SIGUNGU_CODE = os.environ.get("SIGUNGU_CODE", "110012")
DEFAULT_SIDO_CODE = os.environ.get("SIDO_CODE", "110000")


def handler(event, context):
    """
    수동 실행 Lambda.
    심평원 API에서 대상 지역 병원 목록 조회 → SQS에 크롤링 메시지 발행.
    """
    hira = HiraAdapter()
    sqs = SQSAdapter()
    db = DynamoAdapter()

    # 이벤트에서 파라미터 추출 (없으면 기본값 = 성북구)
    sido_code = event.get("sido_code", DEFAULT_SIDO_CODE)
    sigungu_code = event.get("sigungu_code", DEFAULT_SIGUNGU_CODE)

    # 1. 심평원에서 병원 목록 조회
    raw_hospitals = hira.get_hospitals_by_region(
        sido_code=sido_code,
        sigungu_code=sigungu_code,
    )

    # 2. HospitalMeta로 변환 + DynamoDB에 기본 정보 저장
    messages = []
    for raw in raw_hospitals:
        meta = hira.parse_hospital_meta(raw)
        db.save_hospital_meta(meta)

        # 웹사이트 URL이 있는 병원만 크롤링 대상
        # 심평원 데이터에 URL이 없으면 별도 검색 필요 (PoC에서는 스킵)
        website_url = raw.get("hospUrl", "") or ""
        if website_url and website_url.startswith("http"):
            messages.append({
                "hospital_id": meta.hospital_id,
                "website_url": website_url,
                "name": meta.name,
            })

    # 3. SQS에 크롤링 메시지 배치 발행
    sent_count = sqs.send_batch(CRAWL_QUEUE, messages)

    return {
        "status": "triggered",
        "total_hospitals": len(raw_hospitals),
        "crawl_targets": sent_count,
        "skipped_no_url": len(raw_hospitals) - sent_count,
    }
