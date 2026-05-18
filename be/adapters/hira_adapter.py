"""심평원 공공 API 어댑터."""

from __future__ import annotations

import os
from typing import Any

import httpx

from shared.models import HospitalMeta, Location, PublicData

# 심평원 공공 데이터 포털 API
HIRA_BASE_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2"
HIRA_API_KEY = os.environ.get("HIRA_API_KEY", "")


class HiraAdapter:
    def __init__(self):
        self._client = httpx.Client(timeout=30.0)

    def get_hospitals_by_region(
        self,
        sido_code: str = "110000",  # 서울
        sigungu_code: str = "",
        dgsbj_cd: str = "",  # 진료과목 코드
    ) -> list[dict[str, Any]]:
        """심평원에서 지역별 병원 목록 조회."""
        params = {
            "serviceKey": HIRA_API_KEY,
            "pageNo": 1,
            "numOfRows": 1000,
            "sidoCd": sido_code,
            "sgguCd": sigungu_code,
            "dgsbjtCd": dgsbj_cd,
            "xPos": "",
            "yPos": "",
            "radius": "",
            "_type": "json",
        }

        all_items: list[dict] = []
        page = 1

        while True:
            params["pageNo"] = page
            # serviceKey는 이미 인코딩된 상태일 수 있으므로 URL에 직접 삽입
            query_parts = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{HIRA_BASE_URL}/getHospBasisList?{query_parts}"
            resp = self._client.get(url)
            resp.raise_for_status()
            data = resp.json()

            body = data.get("response", {}).get("body", {})
            items = body.get("items", {}).get("item", [])

            if not items:
                break

            if isinstance(items, dict):
                items = [items]

            all_items.extend(items)

            total_count = int(body.get("totalCount", 0))
            if len(all_items) >= total_count:
                break
            page += 1

        return all_items

    def parse_hospital_meta(self, raw: dict[str, Any]) -> HospitalMeta:
        """심평원 응답을 HospitalMeta로 변환."""
        lat = float(raw.get("YPos", 0) or 0)
        lng = float(raw.get("XPos", 0) or 0)

        return HospitalMeta(
            hospital_id=raw.get("ykiho", ""),
            name=raw.get("yadmNm", ""),
            address=raw.get("addr", ""),
            phone=raw.get("telno", ""),
            location=Location(lat=lat, lng=lng, address=raw.get("addr", "")) if lat and lng else None,
            website_url="",
            sido=raw.get("sidoCdNm", ""),
            sigungu=raw.get("sgguCdNm", ""),
        )

    def get_public_data(self, hospital_id: str) -> PublicData:
        """개별 병원의 전문의·의료기기 정보 조회."""
        # 전문의 정보
        specialists = self._get_specialists(hospital_id)
        # 의료기기 정보
        devices = self._get_registered_devices(hospital_id)

        return PublicData(
            license_number=hospital_id,
            specialists=specialists,
            registered_devices=devices,
        )

    def _get_specialists(self, hospital_id: str) -> list[str]:
        """전문의 자격 목록 조회."""
        params = {
            "serviceKey": HIRA_API_KEY,
            "ykiho": hospital_id,
            "pageNo": 1,
            "numOfRows": 50,
            "_type": "json",
        }
        try:
            resp = self._client.get(f"{HIRA_BASE_URL}/getHospBasisList", params=params)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            return [item.get("dgsbjtCdNm", "") for item in items if item.get("dgsbjtCdNm")]
        except Exception:
            return []

    def _get_registered_devices(self, hospital_id: str) -> list[str]:
        """신고된 의료기기 목록 조회."""
        # 심평원 의료기기 API는 별도 엔드포인트
        # PoC에서는 빈 리스트 반환, 추후 구현
        return []
