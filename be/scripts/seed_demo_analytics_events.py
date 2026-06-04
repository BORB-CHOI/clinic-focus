"""Analytics 데모 이벤트 시드.

실행:
    python -m be.scripts.seed_demo_analytics_events --count 180
    python -m be.scripts.seed_demo_analytics_events --dry-run

주의:
  실제 DynamoDB Analytics 테이블에 demo 이벤트를 넣는다. PoC/시연용으로만 사용.
"""

from __future__ import annotations

import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from be.adapters.analytics_adapter import AnalyticsAdapter, EnvContext, HealthEvent, ProfileBucket

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

QUERIES = ["비염", "감기", "여드름", "탈모", "무릎통증", "도수치료", "수면내시경"]
SPECIALTIES = {
    "비염": "이비인후과",
    "감기": "내과",
    "여드름": "피부과",
    "탈모": "피부과",
    "무릎통증": "정형외과",
    "도수치료": "정형외과",
    "수면내시경": "내과",
}
HOSPITALS = [
    ("demo-ent-1", "서울숨이비인후과의원"),
    ("demo-med-1", "강남편한내과의원"),
    ("demo-derm-1", "청담피부클리닉"),
    ("demo-ortho-1", "역삼튼튼정형외과"),
    ("demo-med-2", "선릉바른내과의원"),
]
AGE_BUCKETS = ["20s", "30s", "40s", "50plus", "unknown"]
GENDER_BUCKETS = ["male", "female", "unknown"]
BMI_BUCKETS = ["normal", "overweight", "obese", "unknown"]
TEMP_PROFILES = [
    ("cool", "normal", 16.5, 7.0),
    ("mild", "normal", 21.0, 8.5),
    ("warm", "large", 27.5, 12.0),
    ("hot", "large", 31.0, 13.5),
]
PM25_BUCKETS = [("good", 11.0), ("moderate", 28.0), ("bad", 54.0)]
TIME_BUCKETS = ["morning", "afternoon", "evening"]
EVENT_TYPES = ["impression", "impression", "impression", "click", "click", "select"]


def _event(i: int, rng: random.Random) -> HealthEvent:
    query = rng.choice(QUERIES)
    specialty = SPECIALTIES[query]
    hospital_id, hospital_name = rng.choice(HOSPITALS)
    temp_bucket, temp_diff_bucket, temp_c, temp_diff_c = rng.choice(TEMP_PROFILES)
    pm25_bucket, pm25_value = rng.choice(PM25_BUCKETS)
    event_type = rng.choice(EVENT_TYPES)
    created_at = datetime.now(tz=timezone.utc) - timedelta(hours=rng.randint(0, 24 * 21))

    return HealthEvent(
        event_id=f"demo-{uuid.uuid4()}",
        event_type=event_type,  # type: ignore[arg-type]
        device_id=f"demo-device-{rng.randint(1, 45)}",
        hospital_id=hospital_id,
        hospital_name=hospital_name,
        standard_specialty=specialty,
        sigungu="강남구",
        query=query,
        position=rng.randint(1, 12),
        env=EnvContext(
            temp_bucket=temp_bucket,
            feels_like_bucket=temp_bucket,
            temp_diff_bucket=temp_diff_bucket,
            humidity_bucket=rng.choice(["dry", "normal", "humid"]),
            pm25_bucket=pm25_bucket,
            season="summer",
            time_bucket=rng.choice(TIME_BUCKETS),
            day_type=rng.choice(["weekday", "weekend"]),
            temp_c=temp_c,
            feels_like_c=temp_c + rng.choice([0.0, 0.6, 1.2]),
            temp_diff_c=temp_diff_c,
            humidity_pct=rng.choice([38.0, 54.0, 68.0, 76.0]),
            pm25_value=pm25_value,
            wind_ms=rng.choice([0.8, 1.4, 2.5, 3.2]),
            is_raining=rng.random() < 0.08,
        ),
        profile=ProfileBucket(
            gender_bucket=rng.choice(GENDER_BUCKETS),
            age_bucket=rng.choice(AGE_BUCKETS),
            bmi_bucket=rng.choice(BMI_BUCKETS),
        ),
        created_at=created_at,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic demo analytics events")
    parser.add_argument("--count", type=int, default=180)
    parser.add_argument("--seed", type=int, default=20260603)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    events = [_event(i, rng) for i in range(args.count)]

    if not args.dry_run:
        adapter = AnalyticsAdapter()
        for event in events:
            adapter.put_health_event(event)

    print(f"prepared demo_events={len(events)} dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
