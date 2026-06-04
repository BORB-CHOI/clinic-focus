"""이벤트 집계 스크립트 — 데이터 해자 집계 단계.

DynamoDB에 쌓인 EVENT#click / EVENT#impression / EVENT#select 를 읽어
병원별 CTR·SCR을 계산하고 EVENT#STATS entity로 저장한다.

실행:
  source .venv/bin/activate
  python be/scripts/compute_event_scores.py

주기적으로 (예: 하루 1회) 실행하면 통계가 갱신된다.
검색 API는 이 통계를 읽어 랭킹 보정에 활용할 수 있다 (Phase 2).
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# 루트 기준 실행 지원
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import boto3
from boto3.dynamodb.conditions import Attr

TABLE_NAME = os.environ.get("DYNAMO_TABLE", "kmuproj-10-clinic-Main")


def compute_and_save():
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table(TABLE_NAME)

    # EVENT#* entity 전체 스캔
    print(f"테이블 {TABLE_NAME} 에서 이벤트 스캔 중...")
    counters: dict[str, dict[str, int]] = defaultdict(lambda: {"impression": 0, "click": 0, "select": 0})

    kwargs: dict = {
        "FilterExpression": Attr("entity").begins_with("EVENT#") & ~Attr("entity").eq("EVENT#STATS"),
        "ProjectionExpression": "hospital_id, event_type",
    }
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            hid = item.get("hospital_id")
            etype = item.get("event_type")
            if hid and etype in ("impression", "click", "select"):
                counters[hid][etype] += 1
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    if not counters:
        print("집계할 이벤트 없음.")
        return

    now = datetime.now(tz=timezone.utc).isoformat()
    print(f"병원 {len(counters)}개 통계 저장 중...")

    with table.batch_writer() as batch:
        for hospital_id, c in counters.items():
            impressions = c["impression"]
            clicks = c["click"]
            selects = c["select"]
            ctr = round(clicks / impressions, 4) if impressions > 0 else 0.0
            scr = round(selects / clicks, 4) if clicks > 0 else 0.0

            batch.put_item(Item={
                "hospital_id": hospital_id,
                "entity": "EVENT#STATS",
                "impressions": impressions,
                "clicks": clicks,
                "selects": selects,
                "ctr": str(ctr),   # DynamoDB Decimal 호환
                "scr": str(scr),
                "updated_at": now,
            })
            print(f"  {hospital_id}: 노출 {impressions} / 클릭 {clicks} (CTR {ctr:.1%}) / 선택 {selects} (SCR {scr:.1%})")

    print("완료.")


if __name__ == "__main__":
    compute_and_save()
