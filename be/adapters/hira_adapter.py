"""심평원 공공 API 어댑터."""

from __future__ import annotations

import os
from typing import Any

import httpx

from shared.models import Contact, HospitalMeta, Location, PublicData

# 심평원 공공 데이터 포털 API
HIRA_BASE_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2"
HIRA_API_KEY = os.environ.get("HIRA_API_KEY", "")

# 종별(clCdNm) → 22 standard_specialty 직접 매핑 (평탄화/기타 종별).
# 의원·병원은 진료과목이 list API 에 없으므로(dgsbjtCdNm=null) 병원명에서 파싱.
_CLCD_SPECIALTY: dict[str, str] = {
    "치과의원": "치과", "치과병원": "치과",
    "한의원": "한의원", "한방병원": "한의원",
    "요양병원": "요양병원",
    "종합병원": "종합병원", "상급종합": "종합병원",
    "보건소": "보건소", "보건지소": "보건소", "보건진료소": "보건소", "보건의료원": "보건소",
}

# 병원명 → 양방 16과 파싱 토큰. 순서 중요: 더 긴/구체 과목 먼저
# (정형·신경·성형외과가 "외과"보다, 정신건강의학과가 일반 과목보다 앞).
_NAME_SPECIALTY_ORDER: list[tuple[str, str]] = [
    ("정신건강의학과", "정신건강의학과"), ("정신과", "정신건강의학과"),
    ("마취통증의학과", "마취통증의학과"), ("통증의학과", "마취통증의학과"),
    ("재활의학과", "재활의학과"),
    ("정형외과", "정형외과"),
    ("신경외과", "신경외과"),
    ("성형외과", "성형외과"),
    ("이비인후과", "이비인후과"),
    ("산부인과", "산부인과"),
    ("비뇨의학과", "비뇨의학과"), ("비뇨기과", "비뇨의학과"),
    ("소아청소년과", "소아청소년과"), ("소아과", "소아청소년과"),
    ("가정의학과", "가정의학과"),
    ("피부과", "피부과"),
    ("안과", "안과"),
    ("신경과", "신경과"),
    ("내과", "내과"),
    ("외과", "외과"),  # 마지막 — 다른 ~외과가 모두 걸러진 뒤의 일반 외과
]


def map_standard_specialty(cl_cd_nm: str, name: str) -> str:
    """HIRA 종별(clCdNm) + 병원명으로 22 표준 진료과목 중 하나를 결정한다.

    1) 종별 직접 매핑(치과·한의원·종합병원·요양병원·보건소).
    2) 의원·병원: 병원명에서 양방 진료과 토큰 파싱(한국 의원명은 진료과가 명시됨).
    3) 둘 다 실패 시 '기타'.
    """
    cl = (cl_cd_nm or "").strip()
    if cl in _CLCD_SPECIALTY:
        return _CLCD_SPECIALTY[cl]
    nm = name or ""
    for token, spec in _NAME_SPECIALTY_ORDER:
        if token in nm:
            return spec
    return "기타"


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

        name = raw.get("yadmNm", "")
        return HospitalMeta(
            hospital_id=raw.get("ykiho", ""),
            name=name,
            location=location,
            contact=contact,
            standard_specialty=map_standard_specialty(raw.get("clCdNm", ""), name),
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
