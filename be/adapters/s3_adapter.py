"""S3 어댑터 — 로컬 파일시스템 대체 (S3 권한 없을 때)."""

from __future__ import annotations

import json
import os

from shared.models import CrawlData

DATA_DIR = os.environ.get("CRAWL_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "crawl"))


class S3Adapter:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)

    def save_crawl_data(self, hospital_id: str, data: CrawlData) -> str:
        path = os.path.join(DATA_DIR, f"{hospital_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(data.model_dump_json(indent=2))
        return path

    def load_crawl_data(self, hospital_id: str) -> CrawlData | None:
        path = os.path.join(DATA_DIR, f"{hospital_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return CrawlData.model_validate_json(f.read())

    def save_raw_html(self, hospital_id: str, page_url: str, html: str) -> str:
        dir_path = os.path.join(DATA_DIR, hospital_id, "raw")
        os.makedirs(dir_path, exist_ok=True)
        safe_name = page_url.replace("https://", "").replace("http://", "").replace("/", "_")[:100]
        path = os.path.join(dir_path, f"{safe_name}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return path

    def save_image(self, hospital_id: str, image_bytes: bytes, filename: str) -> str:
        dir_path = os.path.join(DATA_DIR, hospital_id, "images")
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, filename)
        with open(path, "wb") as f:
            f.write(image_bytes)
        return path
