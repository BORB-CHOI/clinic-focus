"""심평원 공공 API 어댑터."""

from __future__ import annotations

import os
from typing import Any

import httpx

from shared.models import Contact, HospitalMeta, Location, PublicData

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
        address = raw.get("addr", "")
        sido = raw.get("sidoCdNm", "")
        sigungu = raw.get("sgguCdNm", "")
        phone = raw.get("telno", "")
        website_url = raw.get("hospUrl", "") or ""

        location = Location(
            address=address,
            lat=lat if lat else None,
            lng=lng if lng else None,
            sido=sido,
            sigungu=sigungu,
        )

        contact = Contact(
            phone=phone if phone else None,
            website_url=website_url if website_url else None,
        )

        return HospitalMeta(
            hospital_id=raw.get("ykiho", ""),
            name=raw.get("yadmNm", ""),
            location=location,
            contact=contact,
        )

    def get_public_data(self, hospital_id: str) -> PublicData:
        """개별 병원의 전문의·의료기기 정보 조회."""
        specialists = self._get_specialists(hospital_id)
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
        return []
