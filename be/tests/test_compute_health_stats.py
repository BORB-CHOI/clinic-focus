from __future__ import annotations

from be.scripts.compute_health_stats import build_insights_stats


def _event(
    event_type: str,
    query: str,
    specialty: str,
    hospital: str,
    *,
    pm25: str = "moderate",
    temp_diff: str = "large",
    age: str = "30s",
) -> dict:
    return {
        "event_type": event_type,
        "query": query,
        "standard_specialty": specialty,
        "hospital_name": hospital,
        "env": {
            "season": "summer",
            "pm25_bucket": pm25,
            "temp_diff_bucket": temp_diff,
            "time_bucket": "morning",
            "temp_c": 28.0,
        },
        "profile": {
            "age_bucket": age,
            "gender_bucket": "female",
            "bmi_bucket": "normal",
        },
    }


def test_build_insights_stats_applies_k_anonymity() -> None:
    events = [
        _event("impression", "비염", "이비인후과", "서울숨이비인후과의원"),
        _event("impression", "비염", "이비인후과", "서울숨이비인후과의원"),
        _event("impression", "비염", "이비인후과", "서울숨이비인후과의원"),
        _event("click", "비염", "이비인후과", "서울숨이비인후과의원"),
        _event("select", "비염", "이비인후과", "서울숨이비인후과의원"),
        _event("click", "희귀검색", "피부과", "청담피부클리닉", pm25="good"),
    ]

    stats = build_insights_stats(events, k=5)

    assert stats["source_event_count"] == 6
    assert stats["metrics"]["weather_coverage"] == 1.0
    assert stats["charts"]["top_queries"] == [{"label": "비염", "count": 5}]
    assert stats["charts"]["top_specialties"] == [{"label": "이비인후과", "count": 5}]
    assert stats["charts"]["hospital_funnel"][0]["label"] == "서울숨이비인후과의원"
    assert stats["charts"]["hospital_funnel"][0]["ctr"] == 0.3333
