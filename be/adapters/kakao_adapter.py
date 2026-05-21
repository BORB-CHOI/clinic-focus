"""카카오 로컬 검색 API 어댑터 — 병원 홈페이지 URL 보강용."""

from __future__ import annotations

import os
from typing import Any

import httpx

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
KAKAO_LOCAL_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoAdapter:
    def __init__(self):
        self._client = httpx.Client(timeout=10.0)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}

    def search_hospital(self, name: str, address: str = "") -> dict[str, Any] | None:
        """
        카카오 로컬 검색으로 병원 정보 조회.
        심평원에 홈페이지 URL 없는 병원의 URL/주소 보강용.
        """
        query = f"{name} {address}".strip()
        params = {
            "query": query,
            "size": 1,
        }

        try:
            resp = self._client.get(
                KAKAO_LOCAL_SEARCH_URL,
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            documents = data.get("documents", [])
            if not documents:
                return None

            doc = documents[0]
            return {
                "place_name": doc.get("place_name", ""),
                "place_url": doc.get("place_url", ""),  # 카카오맵 URL
                "phone": doc.get("phone", ""),
                "address_name": doc.get("address_name", ""),
                "road_address_name": doc.get("road_address_name", ""),
                "x": doc.get("x", ""),  # 경도 (lng)
                "y": doc.get("y", ""),  # 위도 (lat)
                "category_name": doc.get("category_name", ""),
            }
        except Exception:
            return None

    def enrich_hospital_url(self, name: str, address: str = "") -> str | None:
        """병원 홈페이지 URL 조회. 카카오맵 place_url 반환."""
        info = self.search_hospital(name, address)
        if info and info.get("place_url"):
            return info["place_url"]
        return None

    def enrich_hospitals_bulk(
        self, hospitals: list[dict], delay: float = 0.1
    ) -> list[dict]:
        """
        여러 병원의 카카오 정보 보강.
        hospitals: [{"hospital_id": "...", "name": "...", "address": "..."}, ...]
        반환: 각 병원에 kakao_place_url, kakao_phone 등 추가
        """
        import time

        results = []
        for h in hospitals:
            kakao_info = self.search_hospital(h.get("name", ""), h.get("address", ""))
            merged = {**h}
            if kakao_info:
                merged["kakao_place_url"] = kakao_info.get("place_url", "")
                merged["kakao_phone"] = kakao_info.get("phone", "")
                merged["kakao_address"] = kakao_info.get("road_address_name", "") or kakao_info.get("address_name", "")
                merged["kakao_lat"] = kakao_info.get("y", "")
                merged["kakao_lng"] = kakao_info.get("x", "")
            results.append(merged)
            time.sleep(delay)  # API 호출 제한 방지

        return results
