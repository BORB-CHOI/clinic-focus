"""S3 어댑터 — 크롤링 원본 저장 (BE↔AI 중간 저장소).

S3 키 구조:
  crawl/{hospital_id}/crawl_data.json   ← CrawlData 전체 (AI가 읽는 인터페이스)
  crawl/{hospital_id}/raw/{page}.html   ← 원본 HTML
  crawl/{hospital_id}/images/{file}     ← 이미지 (CrawledImage.url = s3://... URI)
"""

from __future__ import annotations

import os

import boto3
from botocore.exceptions import ClientError

from shared.models import CrawlData

BUCKET = os.environ.get("S3_CRAWL_BUCKET", "kmuproj-02-team3-backend")
_PREFIX = "crawl"


class S3Adapter:
    def __init__(self):
        self._s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))

    def save_crawl_data(self, hospital_id: str, data: CrawlData) -> str:
        """CrawlData를 JSON으로 직렬화해 S3에 저장. S3 URI 반환."""
        key = f"{_PREFIX}/{hospital_id}/crawl_data.json"
        self._s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=data.model_dump_json(indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        return f"s3://{BUCKET}/{key}"

    def load_crawl_data(self, hospital_id: str) -> CrawlData | None:
        key = f"{_PREFIX}/{hospital_id}/crawl_data.json"
        try:
            resp = self._s3.get_object(Bucket=BUCKET, Key=key)
            return CrawlData.model_validate_json(resp["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    def save_raw_html(self, hospital_id: str, page_url: str, html: str) -> str:
        """원본 HTML을 S3에 저장. S3 URI 반환."""
        safe_name = (
            page_url.replace("https://", "")
                    .replace("http://", "")
                    .replace("/", "_")[:100]
        )
        key = f"{_PREFIX}/{hospital_id}/raw/{safe_name}.html"
        self._s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        return f"s3://{BUCKET}/{key}"

    def save_image(self, hospital_id: str, image_bytes: bytes, filename: str) -> str:
        """이미지를 S3에 저장. S3 URI 반환 (CrawledImage.url 값으로 사용)."""
        key = f"{_PREFIX}/{hospital_id}/images/{filename}"
        self._s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=image_bytes,
        )
        return f"s3://{BUCKET}/{key}"
