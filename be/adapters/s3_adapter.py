"""S3 어댑터 — 크롤링 원본 저장/로드."""

from __future__ import annotations

import json
import os

import boto3

from shared.models import CrawlData

BUCKET = os.environ.get("CRAWL_BUCKET", "clinic-focus-crawl-data")


class S3Adapter:
    def __init__(self):
        self._client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    def save_crawl_data(self, hospital_id: str, data: CrawlData) -> str:
        key = f"crawl/{hospital_id}/data.json"
        self._client.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=data.model_dump_json(indent=2),
            ContentType="application/json",
        )
        return f"s3://{BUCKET}/{key}"

    def load_crawl_data(self, hospital_id: str) -> CrawlData | None:
        key = f"crawl/{hospital_id}/data.json"
        try:
            resp = self._client.get_object(Bucket=BUCKET, Key=key)
            body = resp["Body"].read().decode("utf-8")
            return CrawlData.model_validate_json(body)
        except self._client.exceptions.NoSuchKey:
            return None

    def save_raw_html(self, hospital_id: str, page_url: str, html: str) -> str:
        """원본 HTML 보관 (디버깅·감사용)."""
        safe_name = page_url.replace("https://", "").replace("http://", "").replace("/", "_")[:100]
        key = f"crawl/{hospital_id}/raw/{safe_name}.html"
        self._client.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=html.encode("utf-8"),
            ContentType="text/html",
        )
        return f"s3://{BUCKET}/{key}"

    def save_image(self, hospital_id: str, image_bytes: bytes, filename: str) -> str:
        key = f"crawl/{hospital_id}/images/{filename}"
        self._client.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=image_bytes,
        )
        return f"s3://{BUCKET}/{key}"
