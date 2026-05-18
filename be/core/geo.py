"""지리 계산 유틸리티."""

from __future__ import annotations

import math


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 간 거리(km) 계산. Haversine 공식."""
    R = 6371.0  # 지구 반지름 (km)

    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def bounding_box(lat: float, lng: float, radius_km: float) -> dict[str, float]:
    """위경도 기준 bounding box 계산. S3 Vectors 메타 필터용."""
    # 위도 1도 ≈ 111km
    lat_delta = radius_km / 111.0
    # 경도 1도 ≈ 111km * cos(lat)
    lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))

    return {
        "lat_min": lat - lat_delta,
        "lat_max": lat + lat_delta,
        "lng_min": lng - lng_delta,
        "lng_max": lng + lng_delta,
    }


def filter_by_radius(
    candidates: list[dict],
    center_lat: float,
    center_lng: float,
    radius_km: float,
) -> list[dict]:
    """후보 리스트에서 반경 내 항목만 필터링 + 거리 추가."""
    results = []
    for item in candidates:
        item_lat = item.get("lat", 0)
        item_lng = item.get("lng", 0)
        dist = haversine(center_lat, center_lng, item_lat, item_lng)
        if dist <= radius_km:
            item["distance_km"] = round(dist, 2)
            results.append(item)
    return results
