"""날씨·환경 컨텍스트 어댑터 — 기상청·에어코리아 공공 API 전용.

두 API 모두 공공데이터포털(data.go.kr)에서 발급, 완전 무료·호출 제한 없음.

  기상청 초단기실황:  KMAS_API_KEY  → 기온(T1H)·습도(REH)·강수형태(PTY)
  에어코리아:        AIRKOREA_API_KEY → PM2.5

키 미설정 또는 API 실패 시 unknown 버킷으로 graceful fallback.
이벤트 저장은 날씨 조회 실패와 무관하게 항상 진행된다.

공공데이터포털 신청:
  기상청: https://apis.data.go.kr → 기상청_단기예보 → 초단기실황조회
  에어코리아: https://apis.data.go.kr → 한국환경공단_에어코리아
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timedelta, timezone

import httpx

from be.adapters.analytics_adapter import (
    EnvContext,
    _day_type,
    _season,
    _time_bucket,
    humidity_bucket,
    pm25_bucket,
    temp_diff_bucket,
    temp_bucket,
)

logger = logging.getLogger(__name__)
_TIMEOUT = 4.0

KST = timezone(timedelta(hours=9))

# ── 기상청 격자 변환 (Lambert Conformal Conic — 기상청 공식 수식) ────────────

def _latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    RE, GRID = 6371.00877, 5.0
    SLAT1, SLAT2, OLON, OLAT = 30.0, 60.0, 126.0, 38.0
    XO, YO = 43, 136
    D = math.pi / 180.0

    re = RE / GRID
    sn = math.log(math.cos(SLAT1 * D) / math.cos(SLAT2 * D)) / math.log(
        math.tan(math.pi * 0.25 + SLAT2 * D * 0.5) /
        math.tan(math.pi * 0.25 + SLAT1 * D * 0.5)
    )
    sf = (math.tan(math.pi * 0.25 + SLAT1 * D * 0.5) ** sn) * math.cos(SLAT1 * D) / sn
    ro = re * sf / (math.tan(math.pi * 0.25 + OLAT * D * 0.5) ** sn)

    ra = re * sf / (math.tan(math.pi * 0.25 + lat * D * 0.5) ** sn)
    theta = (lon - OLON) * D * sn
    if theta >  math.pi: theta -= 2 * math.pi
    if theta < -math.pi: theta += 2 * math.pi

    return int(ra * math.sin(theta) + XO + 0.5), int(ro - ra * math.cos(theta) + YO + 0.5)


def _kmas_base_time() -> tuple[str, str]:
    """초단기실황 base_date·base_time 계산 (KST 기준, 40분 딜레이 반영)."""
    now_kst = datetime.now(tz=KST)
    if now_kst.minute < 40:
        now_kst -= timedelta(hours=1)
    return now_kst.strftime("%Y%m%d"), now_kst.strftime("%H00")


def _kmas_vilage_base_time() -> tuple[str, str]:
    """단기예보 base_date·base_time 계산 (KST 기준, 발표 지연 여유 반영)."""
    now_kst = datetime.now(tz=KST) - timedelta(minutes=10)
    base_hours = (2, 5, 8, 11, 14, 17, 20, 23)
    for hour in reversed(base_hours):
        if now_kst.hour >= hour:
            return now_kst.strftime("%Y%m%d"), f"{hour:02d}00"

    prev_day = now_kst - timedelta(days=1)
    return prev_day.strftime("%Y%m%d"), "2300"


# ── lat/lng → 시도명 (에어코리아 시도별 조회용) ────────────────────────────

_SIDO_BOXES: list[tuple[float, float, float, float, str]] = [
    (37.40, 37.72, 126.73, 127.18, "서울"),
    (37.20, 37.80, 126.40, 127.00, "인천"),
    (35.00, 35.32, 128.90, 129.32, "부산"),
    (35.79, 36.02, 128.40, 128.76, "대구"),
    (35.92, 36.65, 127.28, 127.60, "대전"),
    (35.05, 35.28, 126.60, 127.00, "광주"),
    (35.44, 35.60, 129.22, 129.49, "울산"),
    (35.81, 37.75, 126.55, 129.58, "경기"),
]

def _sido_from_latlon(lat: float, lon: float) -> str:
    for lat_min, lat_max, lon_min, lon_max, sido in _SIDO_BOXES:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return sido
    return "서울"  # 기본값


# ── 공공 API 호출 ────────────────────────────────────────────────────────────

async def _fetch_kmas(client: httpx.AsyncClient, nx: int, ny: int, api_key: str) -> dict:
    base_date, base_time = _kmas_base_time()
    resp = await client.get(
        "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst",
        params={
            "serviceKey": api_key,
            "pageNo":     1,
            "numOfRows":  10,
            "dataType":   "JSON",
            "base_date":  base_date,
            "base_time":  base_time,
            "nx":         nx,
            "ny":         ny,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json()["response"]["body"]["items"]["item"]
    return {row["category"]: row["obsrValue"] for row in items}


async def _fetch_temp_range(client: httpx.AsyncClient, nx: int, ny: int, api_key: str) -> tuple[float, float] | None:
    today = datetime.now(tz=KST).strftime("%Y%m%d")
    for base_date, base_time in _kmas_vilage_base_candidates():
        values = await _fetch_temp_range_at(client, nx, ny, api_key, base_date, base_time, today)
        if values is not None:
            return values
    return None


def _kmas_vilage_base_candidates() -> list[tuple[str, str]]:
    today = datetime.now(tz=KST).strftime("%Y%m%d")
    yesterday = (datetime.now(tz=KST) - timedelta(days=1)).strftime("%Y%m%d")
    candidates = [
        _kmas_vilage_base_time(),
        (today, "0200"),
        (yesterday, "2300"),
    ]

    deduped: list[tuple[str, str]] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


async def _fetch_temp_range_at(
    client: httpx.AsyncClient,
    nx: int,
    ny: int,
    api_key: str,
    base_date: str,
    base_time: str,
    target_date: str,
) -> tuple[float, float] | None:
    resp = await client.get(
        "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
        params={
            "serviceKey": api_key,
            "pageNo":     1,
            "numOfRows":  1000,
            "dataType":   "JSON",
            "base_date":  base_date,
            "base_time":  base_time,
            "nx":         nx,
            "ny":         ny,
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json()["response"]["body"]["items"]["item"]

    values: dict[str, float] = {}
    for row in items:
        if row.get("fcstDate") != target_date:
            continue
        if row.get("category") not in {"TMN", "TMX"}:
            continue
        try:
            values[row["category"]] = float(row["fcstValue"])
        except (ValueError, TypeError):
            continue

    if "TMN" not in values or "TMX" not in values:
        return None
    return values["TMN"], values["TMX"]


async def _fetch_pm25(client: httpx.AsyncClient, sido: str, api_key: str) -> float | None:
    resp = await client.get(
        "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty",
        params={
            "serviceKey": api_key,
            "returnType": "json",
            "numOfRows":  1,
            "pageNo":     1,
            "sidoName":   sido,
            "ver":        "1.0",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json()["response"]["body"]["items"]
    if not items:
        return None
    val = items[0].get("pm25Value")
    try:
        return float(val) if val not in (None, "-", "") else None
    except (ValueError, TypeError):
        return None


def _feels_like_c(temp_c: float, humidity: float, wind_ms: float | None) -> float:
    """간단 체감온도 근사. API 원값이 없어 더위/추위 구간만 보정한다."""
    if temp_c >= 27:
        heat_index = (
            -8.784695
            + 1.61139411 * temp_c
            + 2.338549 * humidity
            - 0.14611605 * temp_c * humidity
            - 0.012308094 * temp_c * temp_c
            - 0.016424828 * humidity * humidity
            + 0.002211732 * temp_c * temp_c * humidity
            + 0.00072546 * temp_c * humidity * humidity
            - 0.000003582 * temp_c * temp_c * humidity * humidity
        )
        return round(heat_index, 1)

    if wind_ms and temp_c <= 10 and wind_ms >= 1.3:
        wind_kmh = wind_ms * 3.6
        wind_chill = 13.12 + 0.6215 * temp_c - 11.37 * (wind_kmh ** 0.16) + 0.3965 * temp_c * (wind_kmh ** 0.16)
        return round(wind_chill, 1)

    return round(temp_c, 1)


# ── 공개 인터페이스 ──────────────────────────────────────────────────────────

async def get_env_context(lat: float, lng: float) -> EnvContext:
    """위치 기반 환경 컨텍스트 조회. 실패 시 unknown 버킷 반환."""
    kmas_key    = os.environ.get("KMAS_API_KEY", "")
    airkorea_key = os.environ.get("AIRKOREA_API_KEY", "")

    if not kmas_key:
        logger.debug("KMAS_API_KEY 미설정 — unknown 버킷 사용")
        return _unknown_context()

    try:
        nx, ny = _latlon_to_grid(lat, lng)
        sido   = _sido_from_latlon(lat, lng)

        async with httpx.AsyncClient() as client:
            kmas_data = await _fetch_kmas(client, nx, ny, kmas_key)

            temp_range: tuple[float, float] | None = None
            try:
                temp_range = await _fetch_temp_range(client, nx, ny, kmas_key)
            except Exception as e:
                logger.debug("기상청 단기예보 일교차 조회 실패 (무시): %s", e)

            pm25: float | None = None
            if airkorea_key:
                try:
                    pm25 = await _fetch_pm25(client, sido, airkorea_key)
                except Exception as e:
                    logger.debug("에어코리아 PM2.5 조회 실패 (무시): %s", e)

        temp_c = float(kmas_data.get("T1H", 15))
        humidity = float(kmas_data.get("REH", 50))
        wind_ms = _parse_float(kmas_data.get("WSD"))
        pty = str(kmas_data.get("PTY", "0"))
        feels_like_c = _feels_like_c(temp_c, humidity, wind_ms)
        temp_diff_c = round(temp_range[1] - temp_range[0], 1) if temp_range else None

        return EnvContext(
            temp_bucket=temp_bucket(temp_c),
            feels_like_bucket=temp_bucket(feels_like_c),
            temp_diff_bucket=temp_diff_bucket(temp_diff_c) if temp_diff_c is not None else "unknown",
            humidity_bucket=humidity_bucket(humidity),
            pm25_bucket=pm25_bucket(pm25) if pm25 is not None else "unknown",
            season=_season(),
            time_bucket=_time_bucket(),
            day_type=_day_type(),
            temp_c=round(temp_c, 1),
            feels_like_c=feels_like_c,
            temp_diff_c=temp_diff_c,
            humidity_pct=round(humidity, 1),
            pm25_value=pm25,
            wind_ms=wind_ms,
            is_raining=pty not in {"0", "없음", ""},
        )

    except Exception as exc:
        logger.warning("기상청 API 조회 실패 (무시): %s", exc)
        return _unknown_context()


def _unknown_context() -> EnvContext:
    return EnvContext(season=_season(), time_bucket=_time_bucket(), day_type=_day_type())


def _parse_float(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "-", "") else None
    except (ValueError, TypeError):
        return None
