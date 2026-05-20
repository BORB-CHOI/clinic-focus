"""병원 1개 크롤링 — EC2 스크립트나 큐 컨슈머에서 직접 호출."""

from __future__ import annotations

import asyncio
import os

import httpx

from be.adapters.hira_adapter import HiraAdapter
from be.adapters.s3_adapter import S3Adapter
from be.adapters.sqs_adapter import SQSAdapter
from be.core.crawler import crawl_one_hospital

INDEX_QUEUE = os.environ.get("INDEX_QUEUE_NAME", "ClinicFocusIndexQueue")


def run_crawl(hospital_id: str, website_url: str) -> dict:
    """
    병원 1개 크롤링 → S3 저장 → 인덱싱 큐에 메시지 발행.
    EC2 스크립트나 큐 컨슈머에서 직접 호출.
    """
    s3 = S3Adapter()
    sqs = SQSAdapter()
    hira = HiraAdapter()

    # 1. 크롤링 실행
    crawl_data = asyncio.run(_crawl(hospital_id, website_url))

    # 2. 심평원 공공 데이터 병합
    try:
        public_data = hira.get_public_data(hospital_id)
        crawl_data.public_data = public_data
    except Exception:
        pass  # 공공 데이터 실패해도 크롤링 결과는 저장

    # 3. S3에 저장
    s3_path = s3.save_crawl_data(hospital_id, crawl_data)

    # 4. 인덱싱 큐에 메시지 발행
    sqs.send_message(INDEX_QUEUE, {
        "hospital_id": hospital_id,
        "s3_path": s3_path,
    })

    return {
        "status": "crawled",
        "hospital_id": hospital_id,
        "pages_count": len(crawl_data.pages),
        "images_count": len(crawl_data.images),
    }


async def _crawl(hospital_id: str, website_url: str):
    async with httpx.AsyncClient() as client:
        return await crawl_one_hospital(hospital_id, website_url, client)
