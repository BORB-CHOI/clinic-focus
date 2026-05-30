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

# V2 single-table 테이블명 — DYNAMO_TABLE 환경변수 우선, 기본값은 팀 테이블명
_DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "kmuproj-10-clinic-Main")

# V2 SK 규약 상수
_SK_FEEDBACK_PREFIX = "FEEDBACK#"
_SK_FEEDBACK_STATS = "FEEDBACK#STATS"   # 집계 entity — 쿼리 결과에서 제외
_SK_CLASSIFICATION = "CLASSIFICATION"


def _get_dynamodb() -> Any:
    """지원 계정 DynamoDB resource 반환. 테스트에서 mock 교체 가능."""
    return get_dynamodb_resource()


def _to_int(value: Any, default: int = 0) -> int:
    """DynamoDB Decimal → int 안전 변환. 변환 불가 값은 default."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def aggregate_feedback_stats(hospital_id: str) -> FeedbackStats:
    """V2 single-table에서 병원별 피드백 통계 집계.

    PK=hospital_id, SK begins_with FEEDBACK# 로 쿼리.
    SK=FEEDBACK#STATS (집계 entity)는 카운트에서 제외한다.
    """
    dynamodb = _get_dynamodb()
    table = dynamodb.Table(_DYNAMO_TABLE)

    # SK begins_with "FEEDBACK#" — 한 병원의 피드백 항목 전체
    response = table.query(
        KeyConditionExpression=(
            Key("hospital_id").eq(hospital_id)
            & Key("entity").begins_with(_SK_FEEDBACK_PREFIX)
        ),
    )
    items = response.get("Items", [])

    # 페이지네이션 처리
    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=(
                Key("hospital_id").eq(hospital_id)
                & Key("entity").begins_with(_SK_FEEDBACK_PREFIX)
            ),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    # FEEDBACK#STATS 집계 entity 제외 — 실제 피드백 건수만 카운트
    feedback_items = [i for i in items if i.get("entity") != _SK_FEEDBACK_STATS]

    total = len(feedback_items)
    agree = sum(1 for i in feedback_items if i.get("verdict") == "agree")
    disagree = total - agree
    agree_ratio = agree / total if total > 0 else 0.0

    last_at = None
    if feedback_items:
        timestamps = [i.get("received_at") for i in feedback_items if i.get("received_at")]
        if timestamps:
            last_at = max(datetime.fromisoformat(str(t)) for t in timestamps)

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
    """피드백 누적 시 신뢰도 재계산. 부정 피드백이 많으면 점수 감점.

    base 분류는 V2 single-table SK=CLASSIFICATION entity 에서 읽는다.
    """
    if len(recent_feedback) < _INSUFFICIENT_FEEDBACK_THRESHOLD:
        raise InsufficientFeedbackError(
            f"피드백이 {len(recent_feedback)}건으로 통계적으로 유의미하지 않음 (최소 {_INSUFFICIENT_FEEDBACK_THRESHOLD}건 필요)"
        )

    dynamodb = _get_dynamodb()
    table = dynamodb.Table(_DYNAMO_TABLE)

    # V2 single-table: PK=hospital_id, SK=CLASSIFICATION
    item = table.get_item(
        Key={"hospital_id": hospital_id, "entity": _SK_CLASSIFICATION}
    ).get("Item", {})

    # confidence 필드 안전 추출 — Decimal 변환 포함
    confidence_data: dict = item.get("confidence", {})
    base_score: int = _to_int(confidence_data.get("score"), default=70)

    raw_signals: dict = confidence_data.get("signals", {})

    # 기여도 비율 보존. 명시적 None(수집 안 됨)은 None 유지 — 가짜 기본값으로
    # 되살리지 않는다(confidence-missing-signals §3 원칙 3). 필드 자체가 없는
    # 옛 레코드만 기본값으로 채운다.
    def _opt_pct(key: str, default: int) -> int | None:
        if key not in raw_signals:
            return default
        raw = raw_signals.get(key)
        return None if raw is None else _to_int(raw, default=default)

    base_signals: dict[str, int | None] = {
        "self_claim": _opt_pct("self_claim", 25),
        "vision": _opt_pct("vision", 0),
        "blog": _opt_pct("blog", 20),
        "reviews": _opt_pct("reviews", 25),
    }

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

    # 긍정 피드백 보정은 수집된(present) 후기 기여도에만 가산. 결손(None)이면 None 유지.
    reviews_base = base_signals["reviews"]
    reviews_out = (
        None if reviews_base is None
        else min(100, reviews_base + int(agree_ratio * 10))
    )
    signals = SignalContributions(
        self_claim=base_signals["self_claim"],
        vision=base_signals["vision"],
        blog=base_signals["blog"],
        reviews=reviews_out,
    )

    return Confidence(score=new_score, level=level, signals=signals)
