"""네이버 지도 API 어댑터 — 병원 검색 + 위치 정보 보강."""

from __future__ import annotations

import os
from typing import Any

import httpx

NAVER_MAP_CLIENT_ID = os.environ.get("NAVER_MAP_CLIENT_ID", "")
NAVER_MAP_CLIENT_SECRET = os.environ.get("NAVER_MAP_CLIENT_SECRET", "")
NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"
NAVER_GEOCODE_URL = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"


class NaverMapAdapter:
    def __init__(self):
        self._client = httpx.Client(timeout=10.0)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Naver-Client-Id": NAVER_MAP_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_MAP_CLIENT_SECRET,
        }

    def search_hospital(self, name: str, address: str = "") -> dict[str, Any] | None:
        """
        네이버 지역 검색으로 병원 정보 조회.
        심평원에 홈페이지 URL 없는 병원의 URL/주소 보강용.
        """
        query = f"{name} {address}".strip()
        params = {
            "query": query,
            "display": 1,
        }

        try:
            resp = self._client.get(
                NAVER_SEARCH_URL,
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            items = data.get("items", [])
            if not items:
                return None

            item = items[0]
            return {
                "title": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                "link": item.get("link", ""),
                "category": item.get("category", ""),
                "address": item.get("address", ""),
                "road_address": item.get("roadAddress", ""),
                "mapx": item.get("mapx", ""),
                "mapy": item.get("mapy", ""),
                "telephone": item.get("telephone", ""),
            }
        except Exception:
            return None

    def search_hospitals_bulk(self, hospitals: list[dict]) -> list[dict]:
        """
        여러 병원을 한번에 검색. 각 병원에 네이버 정보 병합.
        hospitals: [{"name": "...", "address": "..."}, ...]
        """
        results = []
        for h in hospitals:
            naver_info = self.search_hospital(h.get("name", ""), h.get("address", ""))
            merged = {**h}
            if naver_info:
                merged["naver_link"] = naver_info.get("link", "")
                merged["naver_address"] = naver_info.get("road_address", "") or naver_info.get("address", "")
                merged["naver_phone"] = naver_info.get("telephone", "")
                # 네이버 좌표는 카텍 좌표계라 변환 필요 (추후)
                merged["naver_mapx"] = naver_info.get("mapx", "")
                merged["naver_mapy"] = naver_info.get("mapy", "")
            results.append(merged)
        return results

    def get_hospital_website(self, name: str, address: str = "") -> str | None:
        """병원 홈페이지 URL 조회. 심평원에 URL 없을 때 보강용."""
        info = self.search_hospital(name, address)
        if info and info.get("link"):
            return info["link"]
        return None
