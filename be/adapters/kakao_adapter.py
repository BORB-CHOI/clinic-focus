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
        쿼리: "병원명 강남구" — 전체 주소는 오히려 매칭률을 낮춤 (네이버와 동일 전략).
        """
        # 구 우선 추출
        sigungu = ""
        if address:
            parts = address.split()
            sigungu = (
                next((p for p in parts if p.endswith("구")), None)
                or next((p for p in parts if p.endswith("시") and p != "서울특별시"), None)
                or next((p for p in parts if p.endswith("시")), None)
                or ""
            )

        # 긴 이름 단순화
        search_name = name
        for prefix in ("재단법인", "의료법인", "학교법인"):
            if name.startswith(prefix):
                search_name = name[len(prefix):].strip()
                break

        query = f"{search_name} {sigungu}".strip() if sigungu else search_name
        params = {
            "query": query,
            "size": 3,
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

            # 이름 매칭 검증
            name_clean = name.replace(" ", "")
            matched = None
            for doc in documents:
                place_clean = doc.get("place_name", "").replace(" ", "")
                if name_clean in place_clean or place_clean in name_clean:
                    matched = doc
                    break
            if not matched:
                return None

            return {
                "place_name": matched.get("place_name", ""),
                "place_url": matched.get("place_url", ""),  # 카카오맵 URL
                "id": matched.get("id", ""),               # place_url에서 추출 가능, 별도 저장
                "phone": matched.get("phone", ""),
                "address_name": matched.get("address_name", ""),
                "road_address_name": matched.get("road_address_name", ""),
                "x": matched.get("x", ""),  # 경도 (lng)
                "y": matched.get("y", ""),  # 위도 (lat)
                "category_name": matched.get("category_name", ""),
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
