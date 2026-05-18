"""지리 계산 단위 테스트."""

from be.core.geo import bounding_box, filter_by_radius, haversine


def test_haversine_same_point():
    assert haversine(37.5, 127.0, 37.5, 127.0) == 0.0


def test_haversine_known_distance():
    # 서울역 ↔ 강남역 약 8~9km
    dist = haversine(37.5547, 126.9707, 37.4979, 127.0276)
    assert 7.0 < dist < 10.0


def test_bounding_box_3km():
    box = bounding_box(37.5894, 127.0167, 3.0)
    assert box["lat_min"] < 37.5894 < box["lat_max"]
    assert box["lng_min"] < 127.0167 < box["lng_max"]
    # 3km ≈ 0.027도
    assert abs(box["lat_max"] - box["lat_min"] - 2 * 3.0 / 111.0) < 0.001


def test_filter_by_radius():
    candidates = [
        {"hospital_id": "h1", "lat": 37.5894, "lng": 127.0167},  # 중심
        {"hospital_id": "h2", "lat": 37.5900, "lng": 127.0170},  # 매우 가까움
        {"hospital_id": "h3", "lat": 37.6200, "lng": 127.0500},  # 멀리
    ]
    results = filter_by_radius(candidates, 37.5894, 127.0167, 1.0)
    ids = [r["hospital_id"] for r in results]
    assert "h1" in ids
    assert "h2" in ids
    assert "h3" not in ids
