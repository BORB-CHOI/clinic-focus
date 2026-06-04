"""Analytics HEALTH_EVENT 집계 → HEALTH_STATS 저장.

실행:
    python -m be.scripts.compute_health_stats
    python -m be.scripts.compute_health_stats --limit 5000

집계 원칙:
  - raw 이벤트는 DynamoDB Analytics 테이블에만 보관
  - 화면/API에는 k-anonymity 기준(k>=5)을 통과한 셀만 노출
  - 집계 결과는 STATS#INSIGHTS / LATEST 로 저장
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from be.adapters.analytics_adapter import AnalyticsAdapter

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_K = 5
UNKNOWN = "unknown"


def _clean(value: Any, fallback: str = UNKNOWN) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _counter_rows(counter: Counter, *, k: int, limit: int = 12) -> list[dict[str, Any]]:
    rows = [
        {"label": label, "count": count}
        for label, count in counter.most_common()
        if count >= k and label != UNKNOWN
    ]
    return rows[:limit]


def _nested_rows(nested: dict[str, Counter], *, k: int, limit_outer: int = 8, limit_inner: int = 6) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    outer_counts = Counter({outer: sum(counter.values()) for outer, counter in nested.items()})

    for outer, total in outer_counts.most_common(limit_outer):
        if total < k or outer == UNKNOWN:
            continue
        segments = _counter_rows(nested[outer], k=k, limit=limit_inner)
        if segments:
            visible_total = sum(segment["count"] for segment in segments)
            rows.append({"label": outer, "count": visible_total, "segments": segments})

    return rows


def _safe_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator > 0 else 0.0


def build_insights_stats(events: list[dict[str, Any]], *, k: int = DEFAULT_K) -> dict[str, Any]:
    event_type_counts: Counter = Counter()
    query_counts: Counter = Counter()
    specialty_counts: Counter = Counter()
    weather_available = 0
    profile_available = 0

    query_by_season: dict[str, Counter] = defaultdict(Counter)
    query_by_pm25: dict[str, Counter] = defaultdict(Counter)
    query_by_temp_diff: dict[str, Counter] = defaultdict(Counter)
    specialty_by_season: dict[str, Counter] = defaultdict(Counter)
    specialty_by_time: dict[str, Counter] = defaultdict(Counter)
    specialty_by_pm25: dict[str, Counter] = defaultdict(Counter)
    age_by_specialty: dict[str, Counter] = defaultdict(Counter)
    age_gender_by_specialty: dict[str, Counter] = defaultdict(Counter)
    hospital_funnel: dict[str, Counter] = defaultdict(Counter)

    for item in events:
        event_type = _clean(item.get("event_type"))
        query = _clean(item.get("query"))
        specialty = _clean(item.get("standard_specialty"))
        hospital_name = _clean(item.get("hospital_name"))
        env = item.get("env") if isinstance(item.get("env"), dict) else {}
        profile = item.get("profile") if isinstance(item.get("profile"), dict) else {}

        season = _clean(env.get("season"))
        pm25 = _clean(env.get("pm25_bucket"))
        temp_diff = _clean(env.get("temp_diff_bucket"))
        time_bucket = _clean(env.get("time_bucket"))
        age = _clean(profile.get("age_bucket"))
        gender = _clean(profile.get("gender_bucket"))

        event_type_counts[event_type] += 1
        query_counts[query] += 1
        specialty_counts[specialty] += 1

        if env.get("temp_c") is not None or _clean(env.get("temp_bucket")) != UNKNOWN:
            weather_available += 1
        if age != UNKNOWN or _clean(profile.get("gender_bucket")) != UNKNOWN or _clean(profile.get("bmi_bucket")) != UNKNOWN:
            profile_available += 1

        query_by_season[query][season] += 1
        query_by_pm25[query][pm25] += 1
        query_by_temp_diff[query][temp_diff] += 1
        specialty_by_season[season][specialty] += 1
        specialty_by_time[specialty][time_bucket] += 1
        specialty_by_pm25[specialty][pm25] += 1
        age_by_specialty[age][specialty] += 1
        if age != UNKNOWN and gender != UNKNOWN:
            age_gender_by_specialty[f"{age}#{gender}"][specialty] += 1
        hospital_funnel[hospital_name][event_type] += 1

    total = len(events)
    funnel_rows: list[dict[str, Any]] = []
    for hospital, counts in hospital_funnel.items():
        impressions = counts.get("impression", 0)
        clicks = counts.get("click", 0)
        selects = counts.get("select", 0)
        total_hospital_events = impressions + clicks + selects
        if total_hospital_events < k or hospital == UNKNOWN:
            continue
        funnel_rows.append({
            "label": hospital,
            "count": total_hospital_events,
            "impressions": impressions,
            "clicks": clicks,
            "selects": selects,
            "ctr": _safe_rate(clicks, impressions),
            "scr": _safe_rate(selects, max(clicks, selects)),
        })
    funnel_rows.sort(key=lambda row: (row["selects"], row["clicks"], row["count"]), reverse=True)

    return {
        "version": 1,
        "computed_at": datetime.now(tz=timezone.utc).isoformat(),
        "k_anonymity": k,
        "source_event_count": total,
        "metrics": {
            "total_events": total,
            "impressions": event_type_counts.get("impression", 0),
            "clicks": event_type_counts.get("click", 0),
            "selects": event_type_counts.get("select", 0),
            "weather_coverage": _safe_rate(weather_available, total),
            "profile_coverage": _safe_rate(profile_available, total),
        },
        "charts": {
            "top_queries": _counter_rows(query_counts, k=k, limit=10),
            "top_specialties": _counter_rows(specialty_counts, k=k, limit=10),
            "specialty_by_season": _nested_rows(specialty_by_season, k=k, limit_outer=4, limit_inner=6),
            "specialty_by_time": _nested_rows(specialty_by_time, k=k),
            "age_by_specialty": _nested_rows(age_by_specialty, k=k),
            "age_gender_by_specialty": _nested_rows(age_gender_by_specialty, k=k, limit_outer=12, limit_inner=6),
            "query_by_season": _nested_rows(query_by_season, k=k),
            "query_by_pm25": _nested_rows(query_by_pm25, k=k),
            "query_by_temp_diff": _nested_rows(query_by_temp_diff, k=k),
            "specialty_by_pm25": _nested_rows(specialty_by_pm25, k=k),
            "hospital_funnel": funnel_rows[:10],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute ClinicFocus analytics insights")
    parser.add_argument("--limit", type=int, default=None, help="Scan at most N raw events")
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Minimum cell count for exposed stats")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing DynamoDB")
    args = parser.parse_args()

    adapter = AnalyticsAdapter()
    events = adapter.scan_health_events(limit=args.limit)
    stats = build_insights_stats(events, k=args.k)

    if not args.dry_run:
        adapter.put_insights_stats(stats)

    print(
        f"computed source_event_count={stats['source_event_count']} "
        f"k={stats['k_anonymity']} dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
