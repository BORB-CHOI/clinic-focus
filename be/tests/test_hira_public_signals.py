"""심평원 공공 데이터 2종(전문의·비급여) 파싱 단위 테스트.

httpx mock 으로 네트워크 없이 실행 가능.
- 정상 JSON 응답 → 올바른 파싱
- 403 Forbidden → [] / {} graceful degrade
- 필드 누락 → 기본값(0 / None)으로 방어

AWS / Bedrock 호출 없음 (HIRA_API_KEY 불필요).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from be.adapters.hira_adapter import HiraAdapter


# ---------------------------------------------------------------------------
# 헬퍼 — httpx Response mock
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, body: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    if body is not None:
        resp.json.return_value = body
    # 403 이 아닐 때 raise_for_status 는 아무것도 안 함
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def _specialists_body(items: list[dict]) -> dict:
    """getDgsbjtInfo2.7 응답 골격."""
    return {
        "response": {
            "body": {
                "totalCount": len(items),
                "items": {"item": items} if len(items) != 1 else {"item": items[0]},
            }
        }
    }


def _nonpay_body(items: list[dict], total: int | None = None) -> dict:
    """getNonPaymentItemHospDtlList 응답 골격."""
    return {
        "response": {
            "body": {
                "totalCount": total if total is not None else len(items),
                "items": {"item": items} if len(items) != 1 else {"item": items[0]},
            }
        }
    }


# ---------------------------------------------------------------------------
# _get_specialists_by_dept
# ---------------------------------------------------------------------------

class TestGetSpecialistsByDept:
    def setup_method(self):
        self.adapter = HiraAdapter()

    def test_normal_multiple_depts(self):
        """복수 과목 정상 파싱 — specialists_by_dept dict + specialists list."""
        items = [
            {"dgsbjtCdNm": "피부과", "dgsbjtPrSdrCnt": "2"},
            {"dgsbjtCdNm": "내과",   "dgsbjtPrSdrCnt": "1"},
            {"dgsbjtCdNm": "안과",   "dgsbjtPrSdrCnt": "0"},  # 0명 과목
        ]
        body = _specialists_body(items)

        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            by_dept, specialists = self.adapter._get_specialists_by_dept("TEST001")

        assert by_dept == {"피부과": 2, "내과": 1, "안과": 0}
        assert set(specialists) == {"피부과", "내과"}   # 0명 과목 제외
        assert "안과" not in specialists

    def test_single_item_dict_response(self):
        """심평원이 item 1건일 때 dict 로 반환 (list 아님) — 방어 로직 테스트."""
        body = _specialists_body([{"dgsbjtCdNm": "정형외과", "dgsbjtPrSdrCnt": "3"}])
        # _specialists_body 가 1건이면 item[0] dict 로 넣어줌

        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            by_dept, specialists = self.adapter._get_specialists_by_dept("TEST002")

        assert by_dept == {"정형외과": 3}
        assert specialists == ["정형외과"]

    def test_missing_dgsbjtPrSdrCnt_falls_back_to_dtlSdrCnt(self):
        """dgsbjtPrSdrCnt 누락 시 대체 키 dtlSdrCnt 사용."""
        items = [{"dgsbjtCdNm": "이비인후과", "dtlSdrCnt": "1"}]
        body = _specialists_body(items)

        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            by_dept, specialists = self.adapter._get_specialists_by_dept("TEST003")

        assert by_dept["이비인후과"] == 1
        assert "이비인후과" in specialists

    def test_missing_all_count_fields_defaults_to_zero(self):
        """전문의 수 필드 모두 누락 → 0으로 처리, specialists 에서 제외."""
        items = [{"dgsbjtCdNm": "산부인과"}]
        body = _specialists_body(items)

        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            by_dept, specialists = self.adapter._get_specialists_by_dept("TEST004")

        assert by_dept.get("산부인과") == 0
        assert "산부인과" not in specialists

    def test_403_graceful_degrade(self):
        """403 Forbidden → ({}, []) graceful degrade. 키 미승인 상태 시뮬레이션."""
        with patch.object(
            self.adapter._client, "get",
            return_value=_mock_response(403),
        ):
            by_dept, specialists = self.adapter._get_specialists_by_dept("TEST005")

        assert by_dept == {}
        assert specialists == []

    def test_empty_items_returns_empty(self):
        """items 빈 응답 → ({}, [])."""
        body = {"response": {"body": {"totalCount": 0, "items": {}}}}
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            by_dept, specialists = self.adapter._get_specialists_by_dept("TEST006")

        assert by_dept == {}
        assert specialists == []


# ---------------------------------------------------------------------------
# _get_total_doctors
# ---------------------------------------------------------------------------

class TestGetTotalDoctors:
    def setup_method(self):
        self.adapter = HiraAdapter()

    def _total_doctors_body(self, dr_tot_cnt) -> dict:
        return {
            "response": {
                "body": {
                    "items": {"item": {"drTotCnt": dr_tot_cnt}}
                }
            }
        }

    def test_normal(self):
        body = self._total_doctors_body("5")
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            total = self.adapter._get_total_doctors("TEST010")
        assert total == 5

    def test_403_graceful_degrade(self):
        with patch.object(self.adapter._client, "get", return_value=_mock_response(403)):
            total = self.adapter._get_total_doctors("TEST011")
        assert total is None

    def test_missing_drTotCnt(self):
        body = {"response": {"body": {"items": {"item": {}}}}}
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            total = self.adapter._get_total_doctors("TEST012")
        assert total is None


# ---------------------------------------------------------------------------
# _get_nonpay_items
# ---------------------------------------------------------------------------

class TestGetNonpayItems:
    def setup_method(self):
        self.adapter = HiraAdapter()

    def test_normal_parsing(self):
        """정상 비급여 파싱 — 실측 필드: npayKorNm(계층 "대분류/중분류/소분류")·curAmt.

        ★분류 전용 필드는 응답에 없다(clauseCdNm 등 부재). category 는 npayKorNm 의
        첫 세그먼트에서 파생한다(예: "이학요법료/증식치료/척추부위" → "이학요법료").
        """
        items = [
            {"npayKorNm": "이학요법료/증식치료/척추부위", "curAmt": "400000"},
            {"npayKorNm": "초음파검사료(진단초음파)/복부-남성생식기 초음파", "curAmt": "60000"},
        ]
        body = _nonpay_body(items)

        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            result = self.adapter._get_nonpay_items("TEST020")

        assert len(result) == 2
        assert result[0].item_name == "이학요법료/증식치료/척추부위"  # 신고명 그대로(주체명시)
        assert result[0].category == "이학요법료"                    # 첫 세그먼트 파생
        assert result[0].amount == 400000
        assert result[1].category == "초음파검사료(진단초음파)"
        assert result[1].amount == 60000

    def test_flat_name_has_no_category(self):
        """계층 구분자("/") 없는 신고명 → category=None."""
        items = [{"npayKorNm": "도수치료", "curAmt": "80000"}]
        body = _nonpay_body(items)
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            result = self.adapter._get_nonpay_items("TEST020F")
        assert result[0].item_name == "도수치료"
        assert result[0].category is None
        assert result[0].amount == 80000

    def test_range_amount_becomes_none(self):
        """범위 금액("50000~80000") → amount=None."""
        items = [{"npayKorNm": "주사치료", "curAmt": "50000~80000"}]
        body = _nonpay_body(items)

        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            result = self.adapter._get_nonpay_items("TEST021")

        assert result[0].item_name == "주사치료"
        assert result[0].amount is None

    def test_missing_amount_becomes_none(self):
        """curAmt 필드 없음 → amount=None."""
        items = [{"npayKorNm": "MRI촬영"}]
        body = _nonpay_body(items)

        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            result = self.adapter._get_nonpay_items("TEST022")

        assert result[0].amount is None

    def test_403_graceful_degrade(self):
        """403 → [] graceful degrade."""
        with patch.object(self.adapter._client, "get", return_value=_mock_response(403)):
            result = self.adapter._get_nonpay_items("TEST023")
        assert result == []

    def test_itemNm_fallback(self):
        """npayKorNm 없을 때 itemNm 폴백."""
        items = [{"itemNm": "레이저치료", "curAmt": "30000"}]
        body = _nonpay_body(items)

        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            result = self.adapter._get_nonpay_items("TEST024")

        assert result[0].item_name == "레이저치료"
        assert result[0].amount == 30000

    def test_pagination_stops_at_total_count(self):
        """totalCount 가 items 수와 같으면 1페이지에서 멈춤."""
        items = [{"npayKorNm": f"항목{i}", "curAmt": str(i * 1000)} for i in range(5)]
        body = _nonpay_body(items, total=5)

        call_count = 0

        def _get_side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            return _mock_response(200, body)

        with patch.object(self.adapter._client, "get", side_effect=_get_side_effect):
            result = self.adapter._get_nonpay_items("TEST025")

        assert len(result) == 5
        assert call_count == 1  # 1페이지에서 멈춤

    def test_empty_items_returns_empty(self):
        """items 빈 응답({}) → []."""
        body = {"response": {"body": {"totalCount": 0, "items": {}}}}
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            result = self.adapter._get_nonpay_items("TEST026")
        assert result == []

    def test_empty_items_string_returns_empty(self):
        """★실측 함정: 항목 0건이면 HIRA 가 items 를 빈 문자열("")로 준다.

        이전엔 `items.get(...)` 가 AttributeError → except 로 거짓 "호출 실패" 경고.
        의원급은 비급여 신고가 0건이라 이 경로를 항상 타므로 회귀 가드 필수.
        """
        body = {"response": {"body": {"totalCount": 0, "items": ""}}}
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            result = self.adapter._get_nonpay_items("TEST027")
        assert result == []


# ---------------------------------------------------------------------------
# get_public_data 통합
# ---------------------------------------------------------------------------

class TestGetPublicData:
    def setup_method(self):
        self.adapter = HiraAdapter()

    def test_all_403_returns_empty_public_data(self):
        """세 API 모두 403 → PublicData 빈값(graceful degrade 통합)."""
        with patch.object(self.adapter._client, "get", return_value=_mock_response(403)):
            pd = self.adapter.get_public_data("TEST030")

        assert pd.license_number == "TEST030"
        assert pd.specialists_by_dept == {}
        assert pd.specialists == []
        assert pd.total_doctors is None
        assert pd.nonpay_items == []
        assert pd.registered_devices == []

    def test_normal_data_assembled(self):
        """정상 데이터 조합 — specialists_by_dept, nonpay_items 모두 채워짐."""
        specialists_body = _specialists_body(
            [{"dgsbjtCdNm": "피부과", "dgsbjtPrSdrCnt": "1"}]
        )
        total_body = {"response": {"body": {"items": {"item": {"drTotCnt": "3"}}}}}
        nonpay_body_data = _nonpay_body(
            [{"npayKorNm": "보톡스", "clauseCdNm": "주사료", "curAmt": "150000"}]
        )

        call_map = {
            "getDgsbjtInfo2.7": _mock_response(200, specialists_body),
            "getDtlInfo2.7": _mock_response(200, total_body),
            "getNonPaymentItemHospDtlList": _mock_response(200, nonpay_body_data),
        }

        def _dispatch(url, **kwargs):
            for key, resp in call_map.items():
                if key in url:
                    return resp
            return _mock_response(404)

        with patch.object(self.adapter._client, "get", side_effect=_dispatch):
            pd = self.adapter.get_public_data("TEST031")

        assert pd.specialists_by_dept == {"피부과": 1}
        assert pd.specialists == ["피부과"]
        assert pd.total_doctors == 3
        assert len(pd.nonpay_items) == 1
        assert pd.nonpay_items[0].item_name == "보톡스"
        assert pd.nonpay_items[0].amount == 150000
