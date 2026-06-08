"""심평원 공공 API 어댑터."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from shared.models import Contact, HospitalMeta, Location, NonPayItem, PublicData

logger = logging.getLogger(__name__)

# 심평원 공공 데이터 포털 API
HIRA_BASE_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2"
# 의료기관별상세정보서비스 — 서비스 코드 15001699. ★버전 2.8(2.7은 구버전→403/404).
# getDgsbjtInfo2.8(진료과목별 전문의 수)·getMedOftInfo2.8(의료장비). getDtlInfo2.8 은
# 운영시간·주차라 의사수 없음(총 의사 수는 base getHospBasisList 의 drTotCnt 사용).
HIRA_DETAIL_BASE_URL = "https://apis.data.go.kr/B551182/MadmDtlInfoService2.8"
# 비급여진료비 정보 (getNonPaymentItemHospDtlList) — 서비스 코드 15001700
HIRA_NONPAY_BASE_URL = "https://apis.data.go.kr/B551182/nonPaymentDamtInfoService"
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
    ("외과", "외과"),  # 다른 ~외과가 모두 걸러진 뒤의 일반 외과
    # "○○여성의원/여성병원" — 한국에서 '여성의원'은 사실상 산부인과(여성 건강) 종별.
    # 진료과 토큰을 모두 검사한 뒤 맨 마지막에 둬서 "강남여성피부과"는 피부과로,
    # "에스여성의원"처럼 진료과 토큰이 없는 곳만 산부인과로 떨어지게 한다.
    # (이게 없으면 전부 '기타'로 빠져 미용/제모 등 피부과 추론 쿼리에 잘못 노출됨.)
    ("여성", "산부인과"),
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


def _extract_item_list(data: dict) -> list[dict]:
    """HIRA 응답에서 items.item 을 안전하게 list[dict] 로 추출.

    ★실측 함정(2026-06-08): 항목이 0건이면 HIRA 는 items 를 ``{}`` 가 아니라 **빈
    문자열("")** 로 준다. `body.get("items", {}).get(...)` 가정은 이때 AttributeError
    를 던져(거짓 "호출 실패" 경고) — 타입을 확인해 [] 로 정규화한다.
    """
    body = data.get("response", {}).get("body", {})
    items = body.get("items")
    if not isinstance(items, dict):  # "" 또는 None → 항목 없음
        return []
    item = items.get("item")
    if isinstance(item, dict):
        return [item]
    if isinstance(item, list):
        return item
    return []


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
            # ★httpx params= 로 전달해 serviceKey 를 URL-encode 한다. 수동 f"{k}={v}"
            # 조립은 Decoding 키(+, /, = 포함)를 인코딩 안 해 +→공백으로 깨져 401 난다
            # (다른 상세/비급여 메서드는 이미 params= 사용). _extract_item_list 로 빈응답 방어.
            resp = self._client.get(f"{HIRA_BASE_URL}/getHospBasisList", params=params)
            resp.raise_for_status()
            data = resp.json()

            body = data.get("response", {}).get("body", {})
            items = _extract_item_list(data)

            if not items:
                break

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

    def get_public_data(self, hospital_id: str, dr_tot_cnt: int | None = None) -> PublicData:
        """개별 병원의 전문의·의료장비·비급여 정보를 공공 API에서 조회해 PublicData 로 반환.

        - getDgsbjtInfo2.8 → specialists_by_dept(진료과목별 전문의 수)+specialists(과목명 list)
        - getMedOftInfo2.8 → registered_devices(신고 의료장비명)
        - getNonPaymentItemHospDtlList → nonpay_items

        total_doctors(총 의사 수)는 per-ykiho API 가 없어 호출자가 base getHospBasisList 의
        ``drTotCnt`` 를 dr_tot_cnt 로 넘긴다(load_seoul_5gu). 미전달 시 None.
        키/권한 문제(403)·항목 0건에는 각 항목이 빈값으로 graceful degrade.
        """
        specialists_by_dept, specialists = self._get_specialists_by_dept(hospital_id)
        nonpay_items = self._get_nonpay_items(hospital_id)
        devices = self._get_registered_devices(hospital_id)

        return PublicData(
            license_number=hospital_id,
            specialists=specialists,
            registered_devices=devices,
            specialists_by_dept=specialists_by_dept,
            total_doctors=dr_tot_cnt,
            nonpay_items=nonpay_items,
        )

    def _get_specialists_by_dept(self, hospital_id: str) -> tuple[dict[str, int], list[str]]:
        """getDgsbjtInfo2.8 → (specialists_by_dept dict, specialists list).

        - specialists_by_dept: {"피부과": 2, "내과": 1, ...}
          dgsbjtPrSdrCnt(과목별 전문의 수) 기준. 필드 누락 시 대체 키(dtlSdrCnt) 시도 후 0.
        - specialists: 전문의 1명 이상인 과목명만 추린 list
          (기존 _get_specialists 호환 — 검색 필터·표시용).
        403 또는 임의 오류 → ({},[]) graceful degrade.
        """
        params = {
            "serviceKey": HIRA_API_KEY,
            "ykiho": hospital_id,
            "pageNo": "1",
            "numOfRows": "100",
            "_type": "json",
        }
        try:
            resp = self._client.get(
                f"{HIRA_DETAIL_BASE_URL}/getDgsbjtInfo2.8",
                params=params,
            )
            if resp.status_code == 403:
                logger.warning(
                    "HIRA 15001699(getDgsbjtInfo2.8) 미승인(403) — 빈값 degrade. ykiho=%s", hospital_id
                )
                return {}, []
            resp.raise_for_status()
            data = resp.json()
            items = _extract_item_list(data)
            if not items:
                return {}, []

            by_dept: dict[str, int] = {}
            for item in items:
                dept_name: str = (item.get("dgsbjtCdNm") or "").strip()
                if not dept_name:
                    continue
                # dgsbjtPrSdrCnt 우선, 없으면 dtlSdrCnt, 없으면 0
                raw_cnt = item.get("dgsbjtPrSdrCnt") or item.get("dtlSdrCnt") or 0
                try:
                    cnt = int(raw_cnt)
                except (ValueError, TypeError):
                    cnt = 0
                by_dept[dept_name] = by_dept.get(dept_name, 0) + cnt

            specialists = [dept for dept, cnt in by_dept.items() if cnt >= 1]
            return by_dept, specialists

        except Exception as exc:
            logger.warning(
                "HIRA getDgsbjtInfo2.8 호출 실패 (ykiho=%s): %s", hospital_id, exc
            )
            return {}, []

    def _get_nonpay_items(self, hospital_id: str) -> list[NonPayItem]:
        """getNonPaymentItemHospDtlList → 비급여 신고 항목 목록.

        페이지네이션 처리. 403 → [] graceful degrade.
        amount(curAmt): 숫자 파싱 가능하면 int, 범위·문자면 None.
        """
        params = {
            "serviceKey": HIRA_API_KEY,
            "ykiho": hospital_id,
            "pageNo": "1",
            "numOfRows": "100",
            "_type": "json",
        }
        all_items: list[NonPayItem] = []
        page = 1

        try:
            while True:
                params["pageNo"] = str(page)
                resp = self._client.get(
                    f"{HIRA_NONPAY_BASE_URL}/getNonPaymentItemHospDtlList",
                    params=params,
                )
                if resp.status_code == 403:
                    logger.warning(
                        "HIRA 15001700(getNonPaymentItemHospDtlList) 미승인(403) — 빈값 degrade. ykiho=%s",
                        hospital_id,
                    )
                    return []
                resp.raise_for_status()
                data = resp.json()
                body = data.get("response", {}).get("body", {})
                raw_items = _extract_item_list(data)
                if not raw_items:
                    break

                for raw in raw_items:
                    item_name: str = (
                        raw.get("npayKorNm") or raw.get("itemNm") or ""
                    ).strip()
                    if not item_name:
                        continue
                    # ★실측: getNonPaymentItemHospDtlList 에 분류 전용 필드는 없고
                    # npayKorNm 이 "대분류/중분류/소분류" 계층 문자열이다(예: "초음파검사료
                    # (진단초음파)/임산부 초음파/제1삼분기 -일반"). 첫 세그먼트를 분류로 쓴다.
                    category: str | None = (
                        item_name.split("/", 1)[0].strip() if "/" in item_name else None
                    )
                    # curAmt 파싱: 숫자 문자열("50000")→int, 범위("50000~80000")·문자→None
                    raw_amt = raw.get("curAmt")
                    amount: int | None = None
                    if raw_amt is not None:
                        try:
                            amount = int(str(raw_amt).replace(",", "").strip())
                        except (ValueError, TypeError):
                            amount = None

                    all_items.append(
                        NonPayItem(
                            item_name=item_name,
                            category=category if category else None,
                            amount=amount,
                        )
                    )

                total_count = int(body.get("totalCount", 0))
                if len(all_items) >= total_count:
                    break
                page += 1

        except Exception as exc:
            logger.warning(
                "HIRA getNonPaymentItemHospDtlList 호출 실패 (ykiho=%s): %s", hospital_id, exc
            )

        return all_items

    def _get_specialists(self, hospital_id: str) -> list[str]:
        """[레거시 호환] 전문의 과목명 list 반환. 내부는 _get_specialists_by_dept 위임."""
        _, specialists = self._get_specialists_by_dept(hospital_id)
        return specialists

    def _get_registered_devices(self, hospital_id: str) -> list[str]:
        """getMedOftInfo2.8 → 신고된 의료장비명 목록(oftCdNm).

        예: ["CT", "초음파영상진단기", "종양치료기 (Gamma Knife)", "인공호흡기"].
        oftCnt(대수)는 표시 안 하고 장비명만(주체 명시 = 심평원 신고 목록). 의원 등 신고
        장비 0건이면 items="" → []. 403/오류 → [] graceful degrade.
        """
        params = {
            "serviceKey": HIRA_API_KEY,
            "ykiho": hospital_id,
            "pageNo": "1",
            "numOfRows": "100",
            "_type": "json",
        }
        try:
            resp = self._client.get(
                f"{HIRA_DETAIL_BASE_URL}/getMedOftInfo2.8",
                params=params,
            )
            if resp.status_code == 403:
                logger.warning(
                    "HIRA 15001699(getMedOftInfo2.8) 미승인(403) — 빈값 degrade. ykiho=%s", hospital_id
                )
                return []
            resp.raise_for_status()
            data = resp.json()
            items = _extract_item_list(data)
            devices: list[str] = []
            for item in items:
                name = (item.get("oftCdNm") or "").strip()
                if name and name not in devices:
                    devices.append(name)
            return devices
        except Exception as exc:
            logger.warning(
                "HIRA getMedOftInfo2.8 호출 실패 (ykiho=%s): %s", hospital_id, exc
            )
            return []
