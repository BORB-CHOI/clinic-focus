"""Analytics 테이블 어댑터 — kmuproj-02-clinic-Analytics 전용.

Main 테이블(kmuproj-10-clinic-Main)과 완전 분리. 환경 컨텍스트·건강
프로파일·집계 통계를 독자적으로 저장한다.

스키마 (PK=pk, SK=sk):
  HEALTH_EVENT:  pk=EVENT#{device_id}  sk=EVENT#{type}#{ts}
  USER_PROFILE:  pk=PROFILE#{device_id} sk=PROFILE
  HEALTH_STATS:  pk=STATS#QUERY#{q}    sk=STATS
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import boto3
from boto3.dynamodb.conditions import Attr, Key

TABLE_NAME = os.environ.get("ANALYTICS_TABLE", "kmuproj-02-clinic-Analytics")
TTL_SECONDS = 365 * 24 * 3600  # raw 이벤트 1년 후 자동 만료


# ── 도메인 모델 (Analytics 전용, shared/models.py 와 분리) ─────────────────

@dataclass
class EnvContext:
    # ── 버킷 (그룹 분석용) ──────────────────────────────────────
    temp_bucket: str = "unknown"
    feels_like_bucket: str = "unknown"
    temp_diff_bucket: str = "unknown"
    humidity_bucket: str = "unknown"
    pm25_bucket: str = "unknown"
    season: str = "unknown"
    time_bucket: str = "unknown"
    day_type: str = "unknown"
    # ── 실제 수치 (정밀 분석·원시 보관용) ───────────────────────
    temp_c: float | None = None          # 실제 기온 °C
    feels_like_c: float | None = None    # 체감온도 °C
    temp_diff_c: float | None = None     # 일교차 °C (일최고 - 일최저)
    humidity_pct: float | None = None    # 실제 습도 %
    pm25_value: float | None = None      # PM2.5 µg/m³
    wind_ms: float | None = None         # 풍속 m/s
    is_raining: bool = False             # 강수 여부 (PTY != 0)


@dataclass
class ProfileBucket:
    gender_bucket: str = "unknown"
    age_bucket: str = "unknown"
    bmi_bucket: str = "unknown"


@dataclass
class HealthEvent:
    event_id: str
    event_type: Literal["impression", "click", "select"]
    device_id: str
    hospital_id: str
    hospital_name: str
    standard_specialty: str
    sigungu: str
    query: str | None
    position: int | None
    env: EnvContext
    profile: ProfileBucket
    created_at: datetime


@dataclass
class UserProfile:
    device_id: str
    gender_bucket: str
    age_bucket: str
    bmi_bucket: str
    consented_at: datetime


# ── 버킷 계산 유틸 ──────────────────────────────────────────────────────────

def _season() -> str:
    m = datetime.now(tz=timezone.utc).month
    return "spring" if 3 <= m <= 5 else "summer" if 6 <= m <= 8 else "fall" if 9 <= m <= 11 else "winter"


def _time_bucket() -> str:
    h = datetime.now(tz=timezone.utc).hour
    return "dawn" if h < 6 else "morning" if h < 12 else "afternoon" if h < 18 else "evening"


def _day_type() -> str:
    return "weekend" if datetime.now(tz=timezone.utc).weekday() >= 5 else "weekday"


def temp_bucket(c: float) -> str:
    if c < 5:   return "cold"
    if c < 15:  return "cool"
    if c < 23:  return "mild"
    if c < 30:  return "warm"
    return "hot"


def temp_diff_bucket(c: float) -> str:
    if c < 5:   return "small"
    if c < 10:  return "normal"
    if c < 15:  return "large"
    return "very_large"


def humidity_bucket(pct: float) -> str:
    if pct < 40: return "dry"
    if pct < 70: return "normal"
    return "humid"


def pm25_bucket(val: float) -> str:
    if val <= 15: return "good"
    if val <= 35: return "moderate"
    if val <= 75: return "bad"
    return "very_bad"


def _device_hash(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()[:16]


def _float_to_decimal(obj: Any) -> Any:
    if isinstance(obj, float): return Decimal(str(obj))
    if isinstance(obj, dict):  return {k: _float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [_float_to_decimal(i) for i in obj]
    return obj


def _decimal_to_native(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_native(i) for i in obj]
    return obj


# ── 어댑터 ─────────────────────────────────────────────────────────────────

class AnalyticsAdapter:
    def __init__(self) -> None:
        self._table = boto3.resource(
            "dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1")
        ).Table(TABLE_NAME)

    # ── HEALTH_EVENT ──────────────────────────────────────────────────────

    def put_health_event(self, event: HealthEvent) -> None:
        dh = _device_hash(event.device_id)
        ts = event.created_at.isoformat()
        ttl = int(event.created_at.timestamp()) + TTL_SECONDS

        item = _float_to_decimal({
            "pk": f"EVENT#{dh}",
            "sk": f"EVENT#{event.event_type}#{ts}",
            "event_id":           event.event_id,
            "event_type":         event.event_type,
            "hospital_id":        event.hospital_id,
            "hospital_name":      event.hospital_name,
            "standard_specialty": event.standard_specialty,
            "sigungu":            event.sigungu,
            "query":              event.query or "",
            "position":           event.position,
            "env": {
                "temp_bucket":       event.env.temp_bucket,
                "feels_like_bucket": event.env.feels_like_bucket,
                "temp_diff_bucket":  event.env.temp_diff_bucket,
                "humidity_bucket":   event.env.humidity_bucket,
                "pm25_bucket":       event.env.pm25_bucket,
                "season":            event.env.season,
                "time_bucket":       event.env.time_bucket,
                "day_type":          event.env.day_type,
                "temp_c":            event.env.temp_c,
                "feels_like_c":      event.env.feels_like_c,
                "temp_diff_c":       event.env.temp_diff_c,
                "humidity_pct":      event.env.humidity_pct,
                "pm25_value":        event.env.pm25_value,
                "wind_ms":           event.env.wind_ms,
                "is_raining":        event.env.is_raining,
            },
            "profile": {
                "gender_bucket": event.profile.gender_bucket,
                "age_bucket":    event.profile.age_bucket,
                "bmi_bucket":    event.profile.bmi_bucket,
            },
            "created_at": ts,
            "ttl":        ttl,
        })
        self._table.put_item(Item=item)

    # ── USER_PROFILE ──────────────────────────────────────────────────────

    def put_user_profile(self, profile: UserProfile) -> None:
        dh = _device_hash(profile.device_id)
        self._table.put_item(Item={
            "pk":             f"PROFILE#{dh}",
            "sk":             "PROFILE",
            "gender_bucket":  profile.gender_bucket,
            "age_bucket":     profile.age_bucket,
            "bmi_bucket":     profile.bmi_bucket,
            "consented_at":   profile.consented_at.isoformat(),
        })

    def get_user_profile(self, device_id: str) -> ProfileBucket | None:
        dh = _device_hash(device_id)
        resp = self._table.get_item(Key={"pk": f"PROFILE#{dh}", "sk": "PROFILE"})
        item = resp.get("Item")
        if not item:
            return None
        return ProfileBucket(
            gender_bucket=item.get("gender_bucket", "unknown"),
            age_bucket=item.get("age_bucket", "unknown"),
            bmi_bucket=item.get("bmi_bucket", "unknown"),
        )

    def delete_user_profile(self, device_id: str) -> None:
        """삭제권 보장 — opt-out 시 프로파일 제거."""
        dh = _device_hash(device_id)
        self._table.delete_item(Key={"pk": f"PROFILE#{dh}", "sk": "PROFILE"})

    # ── HEALTH_STATS (집계 결과 저장) ─────────────────────────────────────

    def scan_health_events(self, limit: int | None = None) -> list[dict]:
        """Analytics raw 이벤트 전체 스캔. 배치 집계/운영 인사이트 전용."""
        items: list[dict] = []
        kwargs: dict[str, Any] = {
            "FilterExpression": Attr("pk").begins_with("EVENT#") & Attr("sk").begins_with("EVENT#"),
        }

        while True:
            if limit is not None:
                remaining = limit - len(items)
                if remaining <= 0:
                    break
                kwargs["Limit"] = remaining

            resp = self._table.scan(**kwargs)
            items.extend(resp.get("Items", []))

            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key

        return [_decimal_to_native(item) for item in items[:limit]]

    def put_health_stats(self, query: str, stats: dict) -> None:
        self._table.put_item(Item={
            "pk":          f"STATS#QUERY#{query}",
            "sk":          "STATS",
            "stats":       _float_to_decimal(stats),
            "computed_at": datetime.now(tz=timezone.utc).isoformat(),
        })

    def get_health_stats(self, query: str) -> dict | None:
        resp = self._table.get_item(
            Key={"pk": f"STATS#QUERY#{query}", "sk": "STATS"}
        )
        item = resp.get("Item")
        return _decimal_to_native(dict(item["stats"])) if item else None

    def put_insights_stats(self, stats: dict) -> None:
        self._table.put_item(Item={
            "pk":          "STATS#INSIGHTS",
            "sk":          "LATEST",
            "stats":       _float_to_decimal(stats),
            "computed_at": datetime.now(tz=timezone.utc).isoformat(),
        })

    def get_insights_stats(self) -> dict | None:
        resp = self._table.get_item(Key={"pk": "STATS#INSIGHTS", "sk": "LATEST"})
        item = resp.get("Item")
        if not item:
            return None
        stats = _decimal_to_native(dict(item.get("stats", {})))
        stats.setdefault("computed_at", item.get("computed_at"))
        return stats
