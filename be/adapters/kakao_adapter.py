"""카카오맵 API 어댑터 — 병원 홈페이지 URL 검색."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

# 병원명의 괄호는 dapi 검색을 과제약하므로 공백으로 바꿔 푼다 — 단 지점명은 **유지**한다.
# ("해아림한의원(목동점)" → "해아림한의원 목동점"). 지점은 HIRA 상 별개 병원이라 떼면 안 됨.
_PAREN_RE = re.compile(r"[()]+")
# 주소에서 동 토큰 추출 — 같은 구의 다른 지점을 구분하는 검증용.
_DONG_RE = re.compile(r"([가-힣]+\d*동)")


def _dong_token(address: str) -> str:
    """주소에서 법정동/행정동 토큰 추출 (지점 구분용). 없으면 ""."""
    if not address:
        return ""
    m = _DONG_RE.search(address)
    return m.group(1) if m else ""


# 이름 비교용 종별 접미사 — 핵심 토큰만 남겨 place_name 과 대조(오매칭 방지).
_NAME_SUFFIX_RE = re.compile(
    r"(의원|병원|클리닉|치과|한의원|한방병원|피부과|성형외과|정형외과|신경외과|내과|"
    r"이비인후과|안과|산부인과|소아청소년과|소아과|가정의학과|재활의학과|마취통증의학과|"
    r"신경과|비뇨의학과|정신건강의학과|외과|재단법인|의료법인|의료재단|의료원|메디컬)"
)


def _name_core(name: str) -> str:
    """이름 비교용 핵심 토큰: 괄호·공백·종별 접미사 제거."""
    n = _PAREN_RE.sub(" ", name or "")
    n = _NAME_SUFFIX_RE.sub("", n)
    return re.sub(r"\s+", "", n)


def _name_match(doc: dict, core: str) -> bool:
    """검색 결과 place_name 이 병원 핵심 토큰과 일치하는지(양방향 부분일치).

    core 가 2자 미만(흔한 이름)이면 신뢰 못 해 False — 이땐 지역(동/구) 매칭에 의존.
    """
    if len(core) < 2:
        return False
    pn = re.sub(r"\s+", "", doc.get("place_name", "") or "")
    pn_core = _NAME_SUFFIX_RE.sub("", pn)
    return core in pn or (len(pn_core) >= 2 and (pn_core in core or core in pn_core))

KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
KAKAO_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def _region_token(address: str) -> str:
    """주소에서 검색용 지역 토큰(구/시) 추출.

    dapi 키워드 검색에 **full address**(예: "서울특별시 강남구 언주로154길 16, ...빌딩 3층")를
    그대로 넣으면 과제약돼 0건이 나온다(실측). "병원명 + 구" 면 안정적으로 매칭되므로
    구/시 토큰만 뽑아 쓴다.
    """
    if not address:
        return ""
    parts = address.split()
    for p in parts:
        if p.endswith("구"):
            return p
    for p in parts:
        if p.endswith("시") and p != "서울특별시":
            return p
    return parts[0] if parts else ""


class KakaoAdapter:
    def __init__(self):
        self._client = httpx.Client(timeout=10.0)

    def search_hospital(self, name: str, address: str = "") -> dict[str, Any] | None:
        """병원명 + 지역토큰(구)으로 카카오맵 검색. 같은 구의 결과를 우선 반환.

        full address 는 과제약되므로 _region_token 으로 구/시만 사용한다. 동명 병원
        오매칭을 줄이려고 size=5 중 주소에 같은 구가 든 결과를 우선 택한다.
        """
        region = _region_token(address)
        dong = _dong_token(address)
        # 괄호만 공백으로 — 지점명("목동점")은 유지해 카카오가 그 지점을 매칭하게 한다.
        query_name = " ".join(_PAREN_RE.sub(" ", name).split())
        query = f"{query_name} {region}".strip()
        headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
        params = {
            "query": query,
            "category_group_code": "HP8",
            "size": 5,
        }

        try:
            resp = self._client.get(KAKAO_SEARCH_URL, headers=headers, params=params)
            resp.raise_for_status()
            documents = resp.json().get("documents", [])
        except Exception:
            return None

        if not documents:
            return None

        def _addr(d: dict) -> str:
            return f"{d.get('road_address_name', '')} {d.get('address_name', '')}"

        core = _name_core(name)

        def _name_ok(d: dict) -> bool:
            return _name_match(d, core)

        # 우선순위: (동+이름) → (구+이름) → (이름) → (동) → (구).
        # **맹목 docs[0] 폴백 제거** — 이름·지역 어느 것도 안 맞으면 None(틀린 URL/매칭 < 빈값).
        for ok in (
            lambda d: bool(dong) and dong in _addr(d) and _name_ok(d),
            lambda d: bool(region) and region in _addr(d) and _name_ok(d),
            _name_ok,
            lambda d: bool(dong) and dong in _addr(d),
            lambda d: bool(region) and region in _addr(d),
        ):
            for d in documents:
                if ok(d):
                    return d
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
