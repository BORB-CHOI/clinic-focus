from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from be.adapters.analytics_adapter import (
    AnalyticsAdapter,
    EnvContext,
    HealthEvent,
    ProfileBucket,
    temp_diff_bucket,
)
from be.adapters.weather_adapter import KST, _fetch_temp_range


class _FakeResponse:
    def __init__(self, items: list[dict[str, str]]) -> None:
        self._items = items

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"response": {"body": {"items": {"item": self._items}}}}


class _FakeClient:
    def __init__(self, items: list[dict[str, str]]) -> None:
        self.items = items

    async def get(self, *args, **kwargs) -> _FakeResponse:
        return _FakeResponse(self.items)


class _FakeTable:
    def __init__(self) -> None:
        self.item: dict | None = None

    def put_item(self, *, Item: dict) -> None:
        self.item = Item


@pytest.mark.asyncio
async def test_fetch_temp_range_uses_today_tmn_tmx() -> None:
    today = datetime.now(tz=KST).strftime("%Y%m%d")
    client = _FakeClient([
        {"fcstDate": today, "category": "TMP", "fcstValue": "21"},
        {"fcstDate": today, "category": "TMN", "fcstValue": "16.2"},
        {"fcstDate": today, "category": "TMX", "fcstValue": "27.8"},
    ])

    assert await _fetch_temp_range(client, 60, 127, "key") == (16.2, 27.8)


def test_temp_diff_bucket() -> None:
    assert temp_diff_bucket(4.9) == "small"
    assert temp_diff_bucket(8.0) == "normal"
    assert temp_diff_bucket(12.0) == "large"
    assert temp_diff_bucket(16.0) == "very_large"


def test_put_health_event_persists_raw_env_values() -> None:
    table = _FakeTable()
    adapter = AnalyticsAdapter.__new__(AnalyticsAdapter)
    adapter._table = table

    adapter.put_health_event(
        HealthEvent(
            event_id="event-1",
            event_type="click",
            device_id="device-1",
            hospital_id="hospital-1",
            hospital_name="병원",
            standard_specialty="내과",
            sigungu="강남구",
            query="감기",
            position=1,
            env=EnvContext(
                temp_bucket="warm",
                feels_like_bucket="warm",
                temp_diff_bucket="large",
                humidity_bucket="normal",
                pm25_bucket="good",
                season="summer",
                time_bucket="afternoon",
                day_type="weekday",
                temp_c=28.9,
                feels_like_c=30.1,
                temp_diff_c=11.6,
                humidity_pct=62.0,
                pm25_value=12.0,
                wind_ms=1.5,
                is_raining=False,
            ),
            profile=ProfileBucket(),
            created_at=datetime(2026, 6, 3),
        )
    )

    assert table.item is not None
    env = table.item["env"]
    assert env["temp_c"] == Decimal("28.9")
    assert env["feels_like_c"] == Decimal("30.1")
    assert env["temp_diff_c"] == Decimal("11.6")
    assert env["humidity_pct"] == Decimal("62.0")
    assert env["pm25_value"] == Decimal("12.0")
    assert env["wind_ms"] == Decimal("1.5")
    assert env["is_raining"] is False
