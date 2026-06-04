"""Analytics API 라우터 — kmuproj-02-clinic-Analytics 테이블 전용.

Main 테이블 터치 0. FE가 병원 컨텍스트(specialty·sigungu)를 payload에
포함해 전송하므로 BE는 날씨 API만 호출하면 된다.

엔드포인트:
  POST /api/analytics/events   — 환경 컨텍스트 포함 이벤트 저장
  POST /api/analytics/profile  — 건강 프로파일 저장 (opt-in)
  GET  /api/analytics/profile  — 건강 프로파일 조회
  DELETE /api/analytics/profile — 프로파일 삭제 (삭제권 보장)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from be.adapters.analytics_adapter import (
    AnalyticsAdapter,
    EnvContext,
    HealthEvent,
    ProfileBucket,
    UserProfile,
    _season,
    _time_bucket,
)
from be.adapters.weather_adapter import get_env_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])
db = AnalyticsAdapter()


# ── 요청 모델 ───────────────────────────────────────────────────────────────

class AnalyticsEventRequest(BaseModel):
    event_type: Literal["impression", "click", "select"]
    device_id: str
    hospital_id: str
    hospital_name: str
    standard_specialty: str
    sigungu: str
    query: str | None = None
    position: int | None = None
    # 위치 (날씨 조회용 — 없으면 unknown 버킷)
    lat: float | None = None
    lng: float | None = None
    # 건강 프로파일 버킷 (FE에서 계산 후 전달, opt-in 시만)
    gender_bucket: str = "unknown"
    age_bucket: str = "unknown"
    bmi_bucket: str = "unknown"


class ProfileRequest(BaseModel):
    device_id: str
    gender_bucket: Literal["male", "female", "other", "unknown"]
    age_bucket: Literal["teens", "20s", "30s", "40s", "50plus", "unknown"]
    bmi_bucket: Literal["underweight", "normal", "overweight", "obese", "unknown"]


# ── 엔드포인트 ──────────────────────────────────────────────────────────────

@router.post("/events", status_code=201)
async def record_analytics_event(req: AnalyticsEventRequest):
    """환경 컨텍스트 포함 이벤트 저장. 날씨 API 실패해도 이벤트는 저장됨."""
    # 날씨 조회 (async, 실패 시 unknown 버킷으로 fallback)
    env: EnvContext
    if req.lat is not None and req.lng is not None:
        env = await get_env_context(req.lat, req.lng)
    else:
        from be.adapters.analytics_adapter import _season, _time_bucket, _day_type
        env = EnvContext(season=_season(), time_bucket=_time_bucket(), day_type=_day_type())

    # 저장된 프로파일 있으면 우선 사용, 없으면 요청값 사용
    stored_profile = db.get_user_profile(req.device_id)
    profile = stored_profile or ProfileBucket(
        gender_bucket=req.gender_bucket,
        age_bucket=req.age_bucket,
        bmi_bucket=req.bmi_bucket,
    )

    event = HealthEvent(
        event_id=str(uuid.uuid4()),
        event_type=req.event_type,
        device_id=req.device_id,
        hospital_id=req.hospital_id,
        hospital_name=req.hospital_name,
        standard_specialty=req.standard_specialty,
        sigungu=req.sigungu,
        query=req.query,
        position=req.position,
        env=env,
        profile=profile,
        created_at=datetime.now(tz=timezone.utc),
    )

    try:
        db.put_health_event(event)
    except Exception:
        logger.exception("analytics 이벤트 저장 실패 (무시)")

    return {"data": {"event_id": event.event_id}}


@router.post("/profile", status_code=201)
def save_profile(req: ProfileRequest):
    """건강 프로파일 저장 (opt-in). 재호출 시 덮어씀."""
    profile = UserProfile(
        device_id=req.device_id,
        gender_bucket=req.gender_bucket,
        age_bucket=req.age_bucket,
        bmi_bucket=req.bmi_bucket,
        consented_at=datetime.now(tz=timezone.utc),
    )
    db.put_user_profile(profile)
    return {"data": {"saved": True}}


@router.get("/profile")
def get_profile(device_id: str = Query(...)):
    """저장된 건강 프로파일 조회."""
    profile = db.get_user_profile(device_id)
    if not profile:
        return JSONResponse(status_code=404, content={"data": None})
    return {"data": {
        "gender_bucket": profile.gender_bucket,
        "age_bucket":    profile.age_bucket,
        "bmi_bucket":    profile.bmi_bucket,
    }}


@router.delete("/profile", status_code=200)
def delete_profile(device_id: str = Query(...)):
    """프로파일 삭제 — 삭제권(Right to Erasure) 보장."""
    db.delete_user_profile(device_id)
    return {"data": {"deleted": True}}


@router.get("/insights")
def get_insights(
    refresh: bool = Query(False),
    limit: int | None = Query(None, ge=1, le=20000),
):
    """집계 인사이트 조회. refresh=true면 raw 이벤트를 재집계한다."""
    stats = None if refresh else db.get_insights_stats()

    if stats is None:
        from be.scripts.compute_health_stats import build_insights_stats

        events = db.scan_health_events(limit=limit)
        stats = build_insights_stats(events)
        try:
            db.put_insights_stats(stats)
        except Exception:
            logger.exception("analytics 인사이트 저장 실패 (응답은 계속 반환)")

    return {"data": {**stats, "current_season": _season(), "current_time_bucket": _time_bucket()}}


@router.get("/weather")
async def get_weather(lat: float, lng: float):
    """현재 위치 날씨·환경 정보 조회. 지도 페이지 날씨 위젯용."""
    env = await get_env_context(lat, lng)
    return {"data": {
        "temp_bucket":     env.temp_bucket,
        "feels_like_bucket": env.feels_like_bucket,
        "temp_diff_bucket": env.temp_diff_bucket,
        "humidity_bucket": env.humidity_bucket,
        "pm25_bucket":     env.pm25_bucket,
        "season":          env.season,
        "time_bucket":     env.time_bucket,
        "day_type":        env.day_type,
        "temp_c":          env.temp_c,
        "feels_like_c":    env.feels_like_c,
        "temp_diff_c":     env.temp_diff_c,
        "humidity_pct":    env.humidity_pct,
        "pm25_value":      env.pm25_value,
        "wind_ms":         env.wind_ms,
        "is_raining":      env.is_raining,
        "available":       env.temp_bucket != "unknown",
    }}
