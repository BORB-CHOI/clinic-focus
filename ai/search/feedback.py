import os
from datetime import datetime
from typing import Any

from boto3.dynamodb.conditions import Key

from ai.core.aws_clients import get_dynamodb_resource
from ai.core.exceptions import InsufficientFeedbackError
from shared.models import Confidence, FeedbackEntry, FeedbackStats, SignalContributions

_INSUFFICIENT_FEEDBACK_THRESHOLD = 3

_HIGH = int(os.getenv("CONFIDENCE_THRESHOLD_HIGH", "95"))
_LOW = int(os.getenv("CONFIDENCE_THRESHOLD_LOW", "70"))


def _get_dynamodb() -> Any:
    return get_dynamodb_resource()


def aggregate_feedback_stats(hospital_id: str) -> FeedbackStats:
    """DynamoDB Feedback 테이블에서 병원별 피드백 통계 집계."""
    table_name = os.getenv("DYNAMODB_FEEDBACK_TABLE", "Feedback")
    dynamodb = _get_dynamodb()
    table = dynamodb.Table(table_name)

    response = table.query(
        KeyConditionExpression=Key("hospital_id").eq(hospital_id),
    )
    items = response.get("Items", [])

    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=Key("hospital_id").eq(hospital_id),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    total = len(items)
    agree = sum(1 for i in items if i.get("verdict") == "agree")
    disagree = total - agree
    agree_ratio = agree / total if total > 0 else 0.0

    last_at = None
    if items:
        timestamps = [i.get("received_at") for i in items if i.get("received_at")]
        if timestamps:
            last_at = max(datetime.fromisoformat(t) for t in timestamps)

    return FeedbackStats(
        total_count=total,
        agree_count=agree,
        disagree_count=disagree,
        agree_ratio=agree_ratio,
        last_feedback_at=last_at,
    )


def recompute_confidence(
    hospital_id: str,
    recent_feedback: list[FeedbackEntry],
) -> Confidence:
    """피드백 누적 시 신뢰도 재계산. 부정 피드백이 많으면 점수 감점."""
    if len(recent_feedback) < _INSUFFICIENT_FEEDBACK_THRESHOLD:
        raise InsufficientFeedbackError(
            f"피드백이 {len(recent_feedback)}건으로 통계적으로 유의미하지 않음 (최소 {_INSUFFICIENT_FEEDBACK_THRESHOLD}건 필요)"
        )

    table_name = os.getenv("DYNAMODB_CLASSIFICATIONS_TABLE", "Classifications")
    dynamodb = _get_dynamodb()
    table = dynamodb.Table(table_name)

    item = table.get_item(Key={"hospital_id": hospital_id}).get("Item", {})
    base_score: int = item.get("confidence", {}).get("score", 70)
    base_signals: dict[str, int] = item.get("confidence", {}).get("signals", {
        "self_claim": 25, "vision": 0, "blog": 20, "reviews": 25,
    })

    total = len(recent_feedback)
    disagree_count = sum(1 for f in recent_feedback if f.verdict == "disagree")
    disagree_ratio = disagree_count / total

    # 부정 피드백 비율에 따른 감점
    if disagree_ratio >= 0.7:
        penalty = 20
    elif disagree_ratio >= 0.5:
        penalty = 10
    elif disagree_ratio >= 0.3:
        penalty = 5
    else:
        penalty = 0

    # 긍정 피드백 보정
    agree_ratio = 1 - disagree_ratio
    bonus = int(agree_ratio * 5) if agree_ratio >= 0.8 else 0

    new_score = max(0, min(100, base_score - penalty + bonus))

    if new_score >= _HIGH:
        level = "확실"
    elif new_score >= _LOW:
        level = "추정"
    else:
        level = "정보 부족"

    signals = SignalContributions(
        self_claim=base_signals.get("self_claim", 25),
        vision=base_signals.get("vision", 0),
        blog=base_signals.get("blog", 20),
        reviews=min(100, base_signals.get("reviews", 25) + int(agree_ratio * 10)),
    )

    return Confidence(score=new_score, level=level, signals=signals)
