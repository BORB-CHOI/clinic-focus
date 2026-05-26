"""네이버 쿼리 다변화 단위 테스트.

검증 항목:
- 쿼리 변형 순서 (name+구 → name만 → name+동)
- 첫 매칭 시 즉시 중단 (short-circuit)
- 병원명 특수문자 제거
- 동명 추출 로직
- Rate limit 유지
"""

from unittest.mock import patch, MagicMock
import time

import httpx
import pytest

from be.adapters.naver_map_adapter import NaverMapAdapter


def _make_httpx_response(status_code: int, json_data: dict) -> httpx.Response:
    """httpx.Response를 raise_for_status 호환되게 생성."""
    request = httpx.Request("GET", "https://openapi.naver.com/v1/search/local.json")
    return httpx.Response(status_code, json=json_data, request=request)


# ─── _sanitize_name 테스트 ─────────────────────────────────────────────


class TestSanitizeName:
    """병원명 특수문자 제거 로직 검증."""

    def test_removes_parentheses_and_content(self):
        assert NaverMapAdapter._sanitize_name("서울성모병원(강남점)") == "서울성모병원"

    def test_removes_brackets_and_content(self):
        assert NaverMapAdapter._sanitize_name("연세치과[본원]") == "연세치과"

    def test_removes_special_characters(self):
        result = NaverMapAdapter._sanitize_name("서울·강남 피부과&성형외과")
        assert "·" not in result
        assert "&" not in result
        # 한글, 영문, 숫자, 공백만 남아야 함
        assert result == "서울강남 피부과성형외과"

    def test_removes_fullwidth_parentheses(self):
        result = NaverMapAdapter._sanitize_name("미래（서울）의원")
        assert "（" not in result
        assert "）" not in result
        assert result == "미래의원"

    def test_preserves_korean_and_english(self):
        assert NaverMapAdapter._sanitize_name("ABC피부과") == "ABC피부과"

    def test_collapses_multiple_spaces(self):
        result = NaverMapAdapter._sanitize_name("서울  강남  병원")
        assert result == "서울 강남 병원"

    def test_strips_leading_trailing_spaces(self):
        result = NaverMapAdapter._sanitize_name("  서울병원  ")
        assert result == "서울병원"

    def test_no_parens_or_brackets_in_output(self):
        """Property 3: 출력에 괄호/대괄호가 없어야 함."""
        names = [
            "강남(본원)치과",
            "서울[2호점]피부과",
            "미래（강남）의원",
            "연세치과(강남점)[본원]",
            "ABC(가나다)DEF[라마바]의원",
        ]
        for name in names:
            result = NaverMapAdapter._sanitize_name(name)
            assert "(" not in result
            assert ")" not in result
            assert "[" not in result
            assert "]" not in result
            assert "（" not in result
            assert "）" not in result


# ─── _extract_dong 테스트 ──────────────────────────────────────────────


class TestExtractDong:
    """주소에서 동명 추출 로직 검증."""

    def test_extracts_dong_from_parentheses(self):
        address = "서울특별시 강남구 삼성로 123 (대치동)"
        assert NaverMapAdapter._extract_dong(address) == "대치동"

    def test_extracts_dong_from_address_token(self):
        address = "서울특별시 강남구 역삼동 123-4"
        assert NaverMapAdapter._extract_dong(address) == "역삼동"

    def test_parentheses_priority_over_token(self):
        """괄호 안 동명이 토큰보다 우선."""
        address = "서울특별시 강남구 역삼동 123 (대치동)"
        assert NaverMapAdapter._extract_dong(address) == "대치동"

    def test_returns_empty_when_no_dong(self):
        address = "서울특별시 강남구 삼성로 123"
        assert NaverMapAdapter._extract_dong(address) == ""

    def test_handles_numbered_dong(self):
        address = "서울특별시 강남구 역삼1동 123"
        assert NaverMapAdapter._extract_dong(address) == "역삼1동"

    def test_handles_empty_address(self):
        assert NaverMapAdapter._extract_dong("") == ""


# ─── search_hospital_multi_query 테스트 ────────────────────────────────


def _make_naver_response(title: str, link: str = "") -> dict:
    """네이버 검색 API 응답 형식 생성."""
    return {
        "items": [
            {
                "title": f"<b>{title}</b>",
                "link": link,
                "category": "병원>피부과",
                "address": "서울특별시 강남구",
                "roadAddress": "서울특별시 강남구 삼성로 123",
                "mapx": "127.0",
                "mapy": "37.5",
                "telephone": "02-1234-5678",
            }
        ]
    }


def _make_empty_response() -> dict:
    return {"items": []}


class TestSearchHospitalMultiQuery:
    """쿼리 다변화 메서드 통합 테스트."""

    def setup_method(self):
        self.adapter = NaverMapAdapter()

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_returns_first_query_match(self):
        """첫 번째 쿼리(name+구)에서 매칭되면 즉시 반환."""
        response = _make_httpx_response(200, _make_naver_response("강남피부과", "http://gangnam.kr"))

        with patch.object(self.adapter._client, "get", return_value=response) as mock_get:
            result = self.adapter.search_hospital_multi_query(
                "강남피부과", "서울특별시 강남구 역삼동 123"
            )

        assert result is not None
        assert result["link"] == "http://gangnam.kr"
        # 첫 번째 쿼리에서 성공했으므로 1번만 호출
        assert mock_get.call_count == 1

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_falls_through_to_name_only(self):
        """첫 번째 쿼리 실패 → 두 번째 쿼리(name만)로 폴백."""
        responses = [
            _make_httpx_response(200, _make_empty_response()),  # name+구 실패
            _make_httpx_response(200, _make_naver_response("강남피부과", "http://gangnam.kr")),  # name만 성공
        ]

        with patch.object(self.adapter._client, "get", side_effect=responses) as mock_get:
            result = self.adapter.search_hospital_multi_query(
                "강남피부과", "서울특별시 강남구 역삼동 123"
            )

        assert result is not None
        assert result["link"] == "http://gangnam.kr"
        assert mock_get.call_count == 2

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_falls_through_to_dong_query(self):
        """첫 두 쿼리 실패 → 세 번째 쿼리(name+동)로 폴백."""
        responses = [
            _make_httpx_response(200, _make_empty_response()),  # name+구 실패
            _make_httpx_response(200, _make_empty_response()),  # name만 실패
            _make_httpx_response(200, _make_naver_response("강남피부과", "http://gangnam.kr")),  # name+동 성공
        ]

        with patch.object(self.adapter._client, "get", side_effect=responses) as mock_get:
            result = self.adapter.search_hospital_multi_query(
                "강남피부과", "서울특별시 강남구 역삼동 123"
            )

        assert result is not None
        assert result["link"] == "http://gangnam.kr"
        assert mock_get.call_count == 3

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_returns_none_when_all_fail(self):
        """모든 쿼리 실패 시 None 반환."""
        response = _make_httpx_response(200, _make_empty_response())

        with patch.object(self.adapter._client, "get", return_value=response):
            result = self.adapter.search_hospital_multi_query(
                "존재하지않는병원", "서울특별시 강남구 역삼동 123"
            )

        assert result is None

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_short_circuit_on_valid_link(self):
        """
        Property 2: 유효한 link가 있는 결과를 찾으면 나머지 쿼리 실행하지 않음.
        link가 빈 문자열이면 유효하지 않으므로 다음 쿼리로 진행.
        """
        responses = [
            # name+구: 매칭되지만 link 없음 → 유효하지 않음
            _make_httpx_response(200, _make_naver_response("강남피부과", "")),
            # name만: 매칭 + link 있음 → 유효
            _make_httpx_response(200, _make_naver_response("강남피부과", "http://gangnam.kr")),
        ]

        with patch.object(self.adapter._client, "get", side_effect=responses) as mock_get:
            result = self.adapter.search_hospital_multi_query(
                "강남피부과", "서울특별시 강남구 역삼동 123"
            )

        assert result is not None
        assert result["link"] == "http://gangnam.kr"
        # link 없는 결과는 건너뛰고, 두 번째에서 성공 → 세 번째 호출 안 함
        assert mock_get.call_count == 2

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_sanitizes_name_before_query(self):
        """특수문자가 포함된 병원명이 쿼리에서 제거됨."""
        response = _make_httpx_response(200, _make_naver_response("강남피부과", "http://gangnam.kr"))

        with patch.object(self.adapter._client, "get", return_value=response) as mock_get:
            self.adapter.search_hospital_multi_query(
                "강남피부과(본원)", "서울특별시 강남구 역삼동 123"
            )

        # 첫 번째 호출의 쿼리 파라미터 확인
        call_args = mock_get.call_args_list[0]
        query_param = call_args[1]["params"]["query"] if "params" in call_args[1] else call_args[0][1]["query"]
        assert "(" not in query_param
        assert ")" not in query_param
        assert "강남피부과" in query_param

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_query_order_name_gu_then_name_then_dong(self):
        """쿼리 순서가 name+구 → name만 → name+동 인지 확인."""
        response = _make_httpx_response(200, _make_empty_response())

        with patch.object(self.adapter._client, "get", return_value=response) as mock_get:
            self.adapter.search_hospital_multi_query(
                "강남피부과", "서울특별시 강남구 역삼동 123"
            )

        # 3번 호출되어야 함 (모두 실패)
        assert mock_get.call_count == 3

        queries = [
            call[1]["params"]["query"] if "params" in call[1] else ""
            for call in mock_get.call_args_list
        ]
        # 1) name + 구
        assert queries[0] == "강남피부과 강남구"
        # 2) name만
        assert queries[1] == "강남피부과"
        # 3) name + 동
        assert queries[2] == "강남피부과 역삼동"

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_no_dong_skips_third_query(self):
        """동이 없는 주소에서는 세 번째 쿼리를 건너뜀."""
        response = _make_httpx_response(200, _make_empty_response())

        with patch.object(self.adapter._client, "get", return_value=response) as mock_get:
            self.adapter.search_hospital_multi_query(
                "강남피부과", "서울특별시 강남구 삼성로 123"
            )

        # 동이 없으므로 2번만 호출 (name+구, name만)
        assert mock_get.call_count == 2

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_no_address_uses_name_only(self):
        """주소가 없으면 name만으로 단일 쿼리."""
        response = _make_httpx_response(200, _make_empty_response())

        with patch.object(self.adapter._client, "get", return_value=response) as mock_get:
            self.adapter.search_hospital_multi_query("강남피부과", "")

        # 구도 동도 없으므로 1번만 호출
        assert mock_get.call_count == 1

    def test_rate_limit_between_calls(self):
        """API 호출 사이에 rate limit이 유지되는지 확인."""
        call_times: list[float] = []

        def tracking_get(*args, **kwargs):
            call_times.append(time.time())
            return _make_httpx_response(200, _make_empty_response())

        with patch.object(self.adapter._client, "get", side_effect=tracking_get):
            self.adapter.search_hospital_multi_query(
                "강남피부과", "서울특별시 강남구 역삼동 123"
            )

        # 연속 호출 간 간격이 최소 0.12초 이상이어야 함
        for i in range(1, len(call_times)):
            gap = call_times[i] - call_times[i - 1]
            assert gap >= 0.10, f"Call gap {gap:.3f}s is less than rate limit"

    @patch.object(NaverMapAdapter, "RATE_LIMIT_SECONDS", 0.0)
    def test_existing_search_hospital_unchanged(self):
        """기존 search_hospital 메서드가 변경 없이 동작하는지 확인."""
        response = _make_httpx_response(200, _make_naver_response("강남피부과", "http://gangnam.kr"))

        with patch.object(self.adapter._client, "get", return_value=response):
            result = self.adapter.search_hospital("강남피부과", "서울특별시 강남구 역삼동 123")

        assert result is not None
        assert result["link"] == "http://gangnam.kr"
