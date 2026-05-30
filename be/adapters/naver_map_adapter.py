"""네이버 지도 API 어댑터 — 병원 검색 + 위치 정보 보강."""

from __future__ import annotations

import os
import re
import time
from typing import Any

import httpx

NAVER_MAP_CLIENT_ID = os.environ.get("NAVER_MAP_CLIENT_ID", "")
NAVER_MAP_CLIENT_SECRET = os.environ.get("NAVER_MAP_CLIENT_SECRET", "")
NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/local.json"
NAVER_GEOCODE_URL = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"


# 병원명 끝에 붙는 지점·부속 토큰 — 매칭 시 떼어내 본원명만 비교.
# "OO의원 강남점" → "OO의원" 처럼 지점 표기 차이로 인한 오탈락을 막는다.
_BRANCH_SUFFIX_RE = re.compile(
    r"(본원|분원|본점|분점|[가-힣A-Za-z0-9]{1,12}점|[가-힣A-Za-z0-9]{1,12}지점)$"
)


def _strip_branch(name: str) -> str:
    """이름 꼬리의 지점 표기를 1회 제거. ('강남점'·'역삼점'·'본원' 등)"""
    return _BRANCH_SUFFIX_RE.sub("", name).strip()


def _normalize_name(name: str) -> str:
    """매칭용 정규화: 공백 제거 + 지점 토큰 제거.

    공백·지점명 차이를 흡수해 부분문자열 비교 적중률을 높인다.
    """
    no_space = re.sub(r"\s+", "", name or "")
    return _strip_branch(no_space)


def _extract_gu_token(address: str) -> str:
    """주소에서 구(區) 토큰 1개 추출. 없으면 빈 문자열."""
    for part in (address or "").split():
        if part.endswith("구") and len(part) >= 2:
            return part
    return ""


# 동 기준명(숫자 제거) — "역삼1동"·"역삼동" 을 "역삼"으로 맞춰 행정동/법정동 표기차 흡수.
_DONG_BASE_RE = re.compile(r"([가-힣]+)\d*동")


def _extract_dong_base(address: str) -> str:
    """주소에서 동 기준명 추출 (숫자·'동' 제거). 같은 구의 다른 지점 구분용. 없으면 ""."""
    m = _DONG_BASE_RE.search(address or "")
    return m.group(1) if m else ""


class NaverMapAdapter:
    def __init__(self):
        self._client = httpx.Client(timeout=10.0)

    def _headers(self) -> dict[str, str]:
        return {
            "X-Naver-Client-Id": NAVER_MAP_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_MAP_CLIENT_SECRET,
        }

    @staticmethod
    def _is_match(item: dict[str, Any], original_name: str, original_address: str = "") -> bool:
        """검색 결과 1건이 원본 병원과 동일한지 판정.

        완화된 이름 비교 + 구(區) 토큰 일치 요구로 오매칭을 막는다.
          - 이름: 공백·지점명("강남점" 등) 제거 후 양방향 부분문자열 비교
          - 주소: 원본 주소에 구 토큰이 있으면 결과 주소에도 같은 구가 있어야 함
                  (원본에 구 토큰이 없으면 이름 일치만으로 인정)
        """
        title_raw = (
            item.get("title", "")
            .replace("<b>", "")
            .replace("</b>", "")
        )
        name_norm = _normalize_name(original_name)
        title_norm = _normalize_name(title_raw)
        if not name_norm or not title_norm:
            return False
        if not (name_norm in title_norm or title_norm in name_norm):
            return False

        # 구 토큰 교차 검증 — 이름이 흔할 때의 타 지역(다른 구 지점) 오매칭 방지
        gu = _extract_gu_token(original_address)
        item_addr = f"{item.get('address', '')} {item.get('roadAddress', '')}"
        if gu and gu not in item_addr:
            return False

        # 동 교차 검증 — 같은 구의 **다른 지점** 구분. 단 둘 다 동이 잡힐 때만 비교(관대):
        # 결과 주소가 도로명만이라 동이 없으면 거부하지 않는다(행정/법정동 표기차 오탈락 방지).
        dong = _extract_dong_base(original_address)
        if dong:
            item_dong = _extract_dong_base(item_addr)
            if item_dong and item_dong != dong:
                return False
        return True

    def search_hospital(self, name: str, address: str = "") -> dict[str, Any] | None:
        """
        네이버 지역 검색으로 병원 정보 조회.
        쿼리: "병원명 강남구" — 전체 주소는 오히려 매칭률을 낮춤.
        """
        # 주소에서 구 우선 추출 (시보다 구가 더 정확한 검색 단위)
        # "서울특별시 강남구 삼성로..." → "강남구"
        sigungu = ""
        if address:
            parts = address.split()
            sigungu = (
                next((p for p in parts if p.endswith("구")), None)
                or next((p for p in parts if p.endswith("시") and p != "서울특별시"), None)
                or next((p for p in parts if p.endswith("시")), None)
                or ""
            )

        # 긴 이름(재단법인 등) 단순화: 첫 번째 의미 단위만 사용
        search_name = name
        for prefix in ("재단법인", "의료법인", "학교법인"):
            if name.startswith(prefix):
                search_name = name[len(prefix):].strip()
                break

        query = f"{search_name} {sigungu}".strip() if sigungu else search_name

        try:
            resp = self._client.get(
                NAVER_SEARCH_URL,
                headers=self._headers(),
                params={"query": query, "display": 3},
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return None

            # 검색 결과 중 병원명·구 토큰이 일치하는 것만 채택 (완화 매칭)
            for item in items:
                if self._is_match(item, name, address):
                    title_clean = (
                        item.get("title", "")
                        .replace("<b>", "")
                        .replace("</b>", "")
                        .replace(" ", "")
                    )
                    return {
                        "title": title_clean,
                        "link": item.get("link", ""),
                        "category": item.get("category", ""),
                        "address": item.get("address", ""),
                        "road_address": item.get("roadAddress", ""),
                        "mapx": item.get("mapx", ""),
                        "mapy": item.get("mapy", ""),
                        "telephone": item.get("telephone", ""),
                    }
            return None
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

    # ─── 쿼리 다변화 (Task 2) ───────────────────────────────────────────

    RATE_LIMIT_SECONDS: float = 0.12

    def search_hospital_multi_query(self, name: str, address: str = "") -> dict[str, Any] | None:
        """
        쿼리 다변화를 통한 병원 검색.

        쿼리 순서:
          1. sanitized_name + 구
          2. sanitized_name 만
          3. sanitized_name + 동

        첫 번째로 유효한 homepage link가 있는 결과를 찾으면 즉시 반환.
        각 API 호출 사이에 0.12초 rate limit을 유지한다.
        """
        sanitized = self._sanitize_name(name)

        # 주소에서 구/동 추출
        sigungu = ""
        dong = ""
        if address:
            parts = address.split()
            sigungu = (
                next((p for p in parts if p.endswith("구")), None)
                or next((p for p in parts if p.endswith("시") and p != "서울특별시"), None)
                or next((p for p in parts if p.endswith("시")), None)
                or ""
            )
            dong = self._extract_dong(address)

        # 쿼리 변형 목록 구성
        queries: list[str] = []

        # 1) name + 구
        if sigungu:
            queries.append(f"{sanitized} {sigungu}")
        else:
            # 구가 없으면 name만으로 시작
            queries.append(sanitized)

        # 2) name만
        if sigungu:
            queries.append(sanitized)

        # 3) name + 동
        if dong:
            queries.append(f"{sanitized} {dong}")

        last_call_time: float = 0.0

        for query in queries:
            # Rate limit 유지
            elapsed = time.time() - last_call_time
            if last_call_time > 0 and elapsed < self.RATE_LIMIT_SECONDS:
                time.sleep(self.RATE_LIMIT_SECONDS - elapsed)

            result = self._search_with_query(query, name, address)
            last_call_time = time.time()

            if result and result.get("link"):
                return result

        return None

    def _search_with_query(
        self, query: str, original_name: str, original_address: str = ""
    ) -> dict[str, Any] | None:
        """단일 쿼리로 네이버 검색 수행. 병원명·구 토큰 매칭 확인."""
        try:
            resp = self._client.get(
                NAVER_SEARCH_URL,
                headers=self._headers(),
                params={"query": query, "display": 3},
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                return None

            # 매칭 확인: 지점명·공백 제거 후 비교 + 구 토큰 교차 검증.
            # 이름 비교 기준은 특수문자 정리(_sanitize_name)된 원본 이름.
            sanitized_name = self._sanitize_name(original_name)
            for item in items:
                if self._is_match(item, sanitized_name, original_address):
                    title_clean = (
                        item.get("title", "")
                        .replace("<b>", "")
                        .replace("</b>", "")
                        .replace(" ", "")
                    )
                    return {
                        "title": title_clean,
                        "link": item.get("link", ""),
                        "category": item.get("category", ""),
                        "address": item.get("address", ""),
                        "road_address": item.get("roadAddress", ""),
                        "mapx": item.get("mapx", ""),
                        "mapy": item.get("mapy", ""),
                        "telephone": item.get("telephone", ""),
                    }
            return None
        except Exception:
            return None

    @staticmethod
    def _extract_dong(address: str) -> str:
        """
        주소에서 동명 추출.

        우선순위:
          1. 괄호 안 동명: "(대치동)" 패턴
          2. 주소 토큰 중 "동"으로 끝나는 단어 (숫자 제외)
        """
        # 1) 괄호 안 동명 패턴: (대치동), (역삼동) 등
        paren_match = re.search(r"\(([가-힣]+동)\)", address)
        if paren_match:
            return paren_match.group(1)

        # 2) 주소 토큰에서 동 추출
        parts = address.split()
        for part in parts:
            # "동"으로 끝나되, 숫자가 아닌 한글 동명만 (예: "대치동", "역삼1동" 포함)
            if re.match(r"^[가-힣0-9]+동$", part) and len(part) >= 2:
                return part

        return ""

    @staticmethod
    def _sanitize_name(name: str) -> str:
        """
        병원명에서 특수문자 제거.

        - 괄호와 괄호 안 내용 제거: (강남점), [본원], （서울） 등
        - 나머지 특수기호 제거: ·, /, &, + 등
        - 연속 공백 정리
        """
        # 괄호(소/대/전각)와 그 안의 내용 제거
        result = re.sub(r"[(（][^)）]*[)）]", "", name)
        result = re.sub(r"[\[［][^\]］]*[\]］]", "", result)
        # 나머지 특수문자 제거 (한글, 영문, 숫자, 공백만 유지)
        result = re.sub(r"[^\w\s가-힣a-zA-Z0-9]", "", result)
        # 연속 공백 정리
        result = re.sub(r"\s+", " ", result).strip()
        return result
