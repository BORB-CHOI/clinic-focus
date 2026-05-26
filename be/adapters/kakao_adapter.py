"""카카오맵 API 어댑터 — 병원 홈페이지 URL 검색."""

from __future__ import annotations

import os
from typing import Any

import httpx

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
KAKAO_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoAdapter:
    def __init__(self):
        self._client = httpx.Client(timeout=10.0)

    def search_hospital(self, name: str, address: str = "") -> dict[str, Any] | None:
        """병원명 + 주소로 카카오맵 검색. 첫 번째 결과 반환."""
        query = f"{name} {address}".strip()
        headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
        params = {
            "query": query,
            "category_group_code": "HP8",
            "size": 1,
        }

        try:
            resp = self._client.get(KAKAO_SEARCH_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            documents = data.get("documents", [])
            return documents[0] if documents else None
        except Exception:
            return None

    def get_hospital_info(self, name: str, address: str = "") -> dict[str, Any]:
        """병원 검색 결과에서 유용한 정보 추출."""
        result = self.search_hospital(name, address)
        if not result:
            return {}
        return {
            "kakao_id": result.get("id", ""),
            "name": result.get("place_name", ""),
            "address": result.get("road_address_name", "") or result.get("address_name", ""),
            "phone": result.get("phone", ""),
            "category": result.get("category_name", ""),
            "place_url": result.get("place_url", ""),
            "lat": float(result.get("y", 0)),
            "lng": float(result.get("x", 0)),
        }
