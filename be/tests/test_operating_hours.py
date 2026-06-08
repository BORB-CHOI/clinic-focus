"""getDtlInfo2.8 운영시간 파싱 단위 테스트.

네트워크 없이 실행 가능 (httpx mock).
- getDtlInfo2.8 정상 응답 → OperatingHours 파싱
- items="" (종합병원/항목 없음) → None
- 403 → None graceful degrade
- HiraAdapter.get_operating_hours → OperatingHours | None

save/load operating_hours (DynamoAdapter):
- save_public_doctors(operating_hours=...) 저장 후 load_public_doctors 에 operating_hours 반환
- operating_hours 없이 저장 → load 에서 operating_hours=None
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from be.adapters.hira_adapter import (
    HiraAdapter,
    _build_time_range,
    _hhmm_to_str,
    _parse_operating_hours,
)
from be.adapters.dynamo_adapter import DynamoAdapter
from shared.models import OperatingHours, PublicData


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, body: dict | None = None):
    resp = MagicMock()
    resp.status_code = status_code
    if body is not None:
        resp.json.return_value = body
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


def _dtl_body(item: dict) -> dict:
    """getDtlInfo2.8 응답 골격 (item 1건)."""
    return {
        "response": {
            "body": {
                "totalCount": 1,
                "items": {"item": item},
            }
        }
    }


def _dtl_body_empty() -> dict:
    """getDtlInfo2.8 응답 — items="" (종합병원/0건)."""
    return {
        "response": {
            "body": {
                "totalCount": 0,
                "items": "",
            }
        }
    }


# ---------------------------------------------------------------------------
# _hhmm_to_str
# ---------------------------------------------------------------------------

class TestHhmmToStr:
    def test_int_930(self):
        assert _hhmm_to_str(930) == "09:30"

    def test_int_1830(self):
        assert _hhmm_to_str(1830) == "18:30"

    def test_str_0930(self):
        assert _hhmm_to_str("0930") == "09:30"

    def test_str_1000(self):
        assert _hhmm_to_str(1000) == "10:00"

    def test_zero_returns_none(self):
        assert _hhmm_to_str(0) is None

    def test_none_returns_none(self):
        assert _hhmm_to_str(None) is None

    def test_empty_string_returns_none(self):
        assert _hhmm_to_str("") is None

    def test_midnight_edge(self):
        assert _hhmm_to_str(2100) == "21:00"


# ---------------------------------------------------------------------------
# _build_time_range
# ---------------------------------------------------------------------------

class TestBuildTimeRange:
    def test_normal(self):
        assert _build_time_range(930, 1830) == "09:30 ~ 18:30"

    def test_both_none(self):
        assert _build_time_range(None, None) is None

    def test_start_only(self):
        # 종료 없음 → 시작만 반환
        assert _build_time_range(900, None) == "09:00"

    def test_end_only(self):
        assert _build_time_range(None, 1800) == "18:00"


# ---------------------------------------------------------------------------
# _parse_operating_hours
# ---------------------------------------------------------------------------

class TestParseOperatingHours:
    def test_full_item(self):
        """전형적인 의원 — 평일·토·일·점심·주차 모두 있음."""
        item = {
            "trmtMonStart": "0930", "trmtMonEnd": 1830,
            "trmtTueStart": "0930", "trmtTueEnd": 1830,
            "trmtWedStart": "0930", "trmtWedEnd": 1830,
            "trmtThuStart": "0930", "trmtThuEnd": 1930,
            "trmtFriStart": "0930", "trmtFriEnd": 1830,
            "trmtSatStart": "0930", "trmtSatEnd": 1530,
            "noTrmtSun": "휴진",
            "noTrmtHoli": "휴진",
            "lunchWeek": "13:30~14:30",
            "lunchSat": "없음",
            "parkXpnsYn": "N",
            "parkQty": 20,
            "parkEtc": "외래진료 30분 무료",
        }
        oh = _parse_operating_hours(item)
        assert oh is not None
        # 평일 — 월/화/수/금 동일 + 목 다름 → 두 범위 나열
        assert "09:30 ~ 18:30" in oh.weekday
        assert "09:30 ~ 19:30" in oh.weekday
        assert oh.saturday == "09:30 ~ 15:30"
        assert oh.sunday == "휴진"
        assert oh.holiday == "휴진"
        assert oh.lunch_break == "평일 13:30~14:30"  # 토 '없음' 제외
        # 주차: 무료 + parkEtc
        assert oh.parking_note is not None
        assert "무료주차" in oh.parking_note

    def test_uniform_weekday(self):
        """월~금 동일 시간 → 단일 범위."""
        item = {
            "trmtMonStart": 900, "trmtMonEnd": 1800,
            "trmtTueStart": 900, "trmtTueEnd": 1800,
            "trmtWedStart": 900, "trmtWedEnd": 1800,
            "trmtThuStart": 900, "trmtThuEnd": 1800,
            "trmtFriStart": 900, "trmtFriEnd": 1800,
        }
        oh = _parse_operating_hours(item)
        assert oh is not None
        assert oh.weekday == "09:00 ~ 18:00"

    def test_no_trmt_sun_text(self):
        """noTrmtSun 텍스트 → sunday 에 그대로."""
        item = {"noTrmtSun": "휴진", "trmtMonStart": 900, "trmtMonEnd": 1800}
        oh = _parse_operating_hours(item)
        assert oh.sunday == "휴진"

    def test_sun_range(self):
        """trmtSunStart/End 있고 noTrmtSun 없음 → 범위."""
        item = {
            "trmtMonStart": 900, "trmtMonEnd": 1800,
            "trmtSunStart": 1000, "trmtSunEnd": 1400,
        }
        oh = _parse_operating_hours(item)
        assert oh.sunday == "10:00 ~ 14:00"

    def test_notrmt_sun_wins_over_range(self):
        """noTrmtSun 있으면 trmtSunStart/End 무시."""
        item = {
            "trmtMonStart": 900, "trmtMonEnd": 1800,
            "trmtSunStart": 1000, "trmtSunEnd": 1400,
            "noTrmtSun": "공휴일 포함 휴진",
        }
        oh = _parse_operating_hours(item)
        assert oh.sunday == "공휴일 포함 휴진"

    def test_lunch_sat_included(self):
        """lunchSat 값이 '없음' 아닌 경우 lunch_break 에 포함."""
        item = {
            "trmtMonStart": 900, "trmtMonEnd": 1800,
            "lunchWeek": "12:30~13:30",
            "lunchSat": "12:00~13:00",
        }
        oh = _parse_operating_hours(item)
        assert "토 12:00~13:00" in oh.lunch_break

    def test_parking_paid(self):
        """parkXpnsYn=Y → 유료주차."""
        item = {
            "trmtMonStart": 900, "trmtMonEnd": 1800,
            "parkXpnsYn": "Y",
            "parkQty": 10,
        }
        oh = _parse_operating_hours(item)
        assert "유료주차" in oh.parking_note

    def test_all_empty_returns_none(self):
        """유의미한 필드 없음 → None."""
        oh = _parse_operating_hours({})
        assert oh is None

    def test_empty_notrmt_fields_only(self):
        """noTrmtSun/Holi 빈 문자열 → sunday/holiday None."""
        item = {
            "trmtMonStart": 900, "trmtMonEnd": 1800,
            "noTrmtSun": "",
            "noTrmtHoli": "",
        }
        oh = _parse_operating_hours(item)
        assert oh is not None
        assert oh.sunday is None
        assert oh.holiday is None


# ---------------------------------------------------------------------------
# HiraAdapter.get_operating_hours
# ---------------------------------------------------------------------------

class TestGetOperatingHours:
    def setup_method(self):
        self.adapter = HiraAdapter()

    def test_normal_item(self):
        """정상 응답 → OperatingHours 반환."""
        item = {
            "trmtMonStart": "0930", "trmtMonEnd": 1830,
            "trmtTueStart": "0930", "trmtTueEnd": 1830,
            "trmtWedStart": "0930", "trmtWedEnd": 1830,
            "trmtThuStart": "0930", "trmtThuEnd": 1830,
            "trmtFriStart": "0930", "trmtFriEnd": 1830,
            "noTrmtSun": "휴진",
            "noTrmtHoli": "휴진",
        }
        body = _dtl_body(item)
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            oh = self.adapter.get_operating_hours("TEST_OH_001")
        assert isinstance(oh, OperatingHours)
        assert oh.weekday == "09:30 ~ 18:30"
        assert oh.sunday == "휴진"
        assert oh.holiday == "휴진"

    def test_empty_items_returns_none(self):
        """items="" (종합병원/0건) → None."""
        body = _dtl_body_empty()
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            oh = self.adapter.get_operating_hours("TEST_OH_002")
        assert oh is None

    def test_403_returns_none(self):
        """403 → None graceful degrade."""
        with patch.object(self.adapter._client, "get", return_value=_mock_response(403)):
            oh = self.adapter.get_operating_hours("TEST_OH_003")
        assert oh is None

    def test_all_meaningful_fields_none_returns_none(self):
        """getDtlInfo2.8 응답이 있지만 의미 있는 값 없음 → None."""
        item = {}  # 빈 dict
        body = _dtl_body(item)
        with patch.object(self.adapter._client, "get", return_value=_mock_response(200, body)):
            oh = self.adapter.get_operating_hours("TEST_OH_004")
        assert oh is None


# ---------------------------------------------------------------------------
# DynamoAdapter save/load operating_hours
# ---------------------------------------------------------------------------

class TestDynamoOperatingHours:
    """DynamoDB mock 으로 save/load operating_hours 테스트."""

    def _make_adapter(self) -> DynamoAdapter:
        adapter = DynamoAdapter.__new__(DynamoAdapter)
        adapter._resource = MagicMock()
        adapter._table = MagicMock()
        return adapter

    def test_save_with_operating_hours(self):
        """save_public_doctors 에 operating_hours 전달 → put_entity 에 포함."""
        adapter = self._make_adapter()
        adapter._table.put_item = MagicMock()

        pd = PublicData(
            license_number="TEST001",
            specialists=[],
            registered_devices=[],
        )
        oh = OperatingHours(
            weekday="09:30 ~ 18:30",
            sunday="휴진",
            holiday="휴진",
            lunch_break="평일 13:30~14:30",
            parking_note="무료주차 20대 가능",
        )
        adapter.save_public_doctors("TEST001", pd, operating_hours=oh)

        # put_item 이 호출됐는지 + operating_hours 필드 포함 확인
        assert adapter._table.put_item.called
        call_item = adapter._table.put_item.call_args[1]["Item"]
        assert "operating_hours" in call_item
        oh_saved = call_item["operating_hours"]
        assert oh_saved.get("weekday") == "09:30 ~ 18:30"
        assert oh_saved.get("sunday") == "휴진"
        assert oh_saved.get("parking_note") == "무료주차 20대 가능"

    def test_save_without_operating_hours(self):
        """operating_hours=None → put_entity 에 operating_hours 키 없음."""
        adapter = self._make_adapter()
        adapter._table.put_item = MagicMock()

        pd = PublicData(
            license_number="TEST002",
            specialists=["피부과"],
            registered_devices=[],
        )
        adapter.save_public_doctors("TEST002", pd, operating_hours=None)

        call_item = adapter._table.put_item.call_args[1]["Item"]
        assert "operating_hours" not in call_item

    def test_load_with_operating_hours(self):
        """load_public_doctors → operating_hours: OperatingHours 반환."""
        adapter = self._make_adapter()
        adapter._table.get_item = MagicMock(return_value={
            "Item": {
                "hospital_id": "TEST003",
                "entity": "PUBLIC#DOCTORS",
                "specialists_by_dept": {"피부과": Decimal("2")},
                "specialists": ["피부과"],
                "registered_devices": ["레이저치료기"],
                "total_doctors": Decimal("3"),
                "operating_hours": {
                    "weekday": "09:00 ~ 18:00",
                    "saturday": "09:00 ~ 13:00",
                    "sunday": "휴진",
                    "holiday": "휴진",
                    "lunch_break": "평일 13:00~14:00",
                    "parking_note": "무료주차 10대 가능",
                },
            }
        })
        result = adapter.load_public_doctors("TEST003")

        oh = result.get("operating_hours")
        assert isinstance(oh, OperatingHours)
        assert oh.weekday == "09:00 ~ 18:00"
        assert oh.saturday == "09:00 ~ 13:00"
        assert oh.sunday == "휴진"
        assert oh.parking_note == "무료주차 10대 가능"

    def test_load_without_operating_hours(self):
        """operating_hours 필드 없는 기존 entity → operating_hours=None."""
        adapter = self._make_adapter()
        adapter._table.get_item = MagicMock(return_value={
            "Item": {
                "hospital_id": "TEST004",
                "entity": "PUBLIC#DOCTORS",
                "specialists_by_dept": {},
                "specialists": [],
                "registered_devices": [],
            }
        })
        result = adapter.load_public_doctors("TEST004")
        assert result.get("operating_hours") is None

    def test_load_empty_entity_returns_empty_dict(self):
        """entity 없음 → {}."""
        adapter = self._make_adapter()
        adapter._table.get_item = MagicMock(return_value={})
        result = adapter.load_public_doctors("TEST005")
        assert result == {}
        assert result.get("operating_hours") is None
