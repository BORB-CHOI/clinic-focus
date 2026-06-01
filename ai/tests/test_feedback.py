"""test_feedback.py — ai/search/feedback.py V2 single-table 쿼리 단위 테스트.

실행:
    .venv/bin/python -m pytest ai/tests/ -q

모든 테스트는 DynamoDB / AWS 실 호출을 발생시키지 않는다.
boto3 resource 는 unittest.mock.patch 로 완전히 차단하며 assert_not_called 불필요.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from shared.models import FeedbackEntry, FeedbackStats, Confidence
from ai.core.exceptions import InsufficientFeedbackError


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------

def _make_feedback_entry(
    verdict: str = "agree",
    feedback_id: str = "fb-001",
    device_id: str = "dev-001",
    ts: str = "2026-05-28T10:00:00+00:00",
) -> FeedbackEntry:
    """FeedbackEntry 픽스처 생성 헬퍼."""
    return FeedbackEntry(
        feedback_id=feedback_id,
        hospital_id="h-001",
        device_id=device_id,
        primary_focus="척추",
        verdict=verdict,
        received_at=datetime.fromisoformat(ts),
    )


def _make_ddb_feedback_item(
    sk: str,
    verdict: str = "agree",
    received_at: str = "2026-05-28T10:00:00+00:00",
) -> dict:
    """DynamoDB FEEDBACK# 항목 mock 딕셔너리."""
    return {
        "hospital_id": "h-001",
        "entity": sk,
        "verdict": verdict,
        "received_at": received_at,
    }


def _make_mock_table(query_items: list[dict], get_item_response: dict | None = None) -> MagicMock:
    """DynamoDB Table mock 생성. query 는 단일 페이지, get_item 은 선택적."""
    table = MagicMock()
    table.query.return_value = {"Items": query_items}
    if get_item_response is not None:
        table.get_item.return_value = {"Item": get_item_response}
    else:
        table.get_item.return_value = {}
    return table


def _make_mock_resource(table_mock: MagicMock) -> MagicMock:
    """DynamoDB resource mock — .Table() 호출 시 table_mock 반환."""
    resource = MagicMock()
    resource.Table.return_value = table_mock
    return resource


# ---------------------------------------------------------------------------
# TestAggregateFeedbackStats
# ---------------------------------------------------------------------------

class TestAggregateFeedbackStats:
    """aggregate_feedback_stats V2 single-table 쿼리 검증."""

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_basic_agree_disagree_count(self, mock_get_resource: MagicMock) -> None:
        """FEEDBACK# 항목 3건(agree 2, disagree 1) → total=3, agree=2, agree_ratio≈0.667."""
        from ai.search.feedback import aggregate_feedback_stats

        items = [
            _make_ddb_feedback_item("FEEDBACK#dev-001#2026-05-28T10:00:00", "agree"),
            _make_ddb_feedback_item("FEEDBACK#dev-002#2026-05-28T11:00:00", "agree"),
            _make_ddb_feedback_item("FEEDBACK#dev-003#2026-05-28T12:00:00", "disagree"),
        ]
        table_mock = _make_mock_table(query_items=items)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        result = aggregate_feedback_stats("h-001")

        assert result.total_count == 3
        assert result.agree_count == 2
        assert result.disagree_count == 1
        assert abs(result.agree_ratio - 2 / 3) < 1e-6

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_feedback_stats_entity_excluded(self, mock_get_resource: MagicMock) -> None:
        """SK=FEEDBACK#STATS 집계 entity는 total_count에 포함되면 안 된다."""
        from ai.search.feedback import aggregate_feedback_stats

        items = [
            _make_ddb_feedback_item("FEEDBACK#dev-001#2026-05-28T10:00:00", "agree"),
            _make_ddb_feedback_item("FEEDBACK#dev-002#2026-05-28T11:00:00", "disagree"),
            # 집계 entity — 제외 대상
            {
                "hospital_id": "h-001",
                "entity": "FEEDBACK#STATS",
                "total": 100,
                "agree": 80,
            },
        ]
        table_mock = _make_mock_table(query_items=items)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        result = aggregate_feedback_stats("h-001")

        # FEEDBACK#STATS 가 제외되어 실제 피드백 건수만 카운트
        assert result.total_count == 2, (
            f"total_count={result.total_count} — FEEDBACK#STATS 포함 의심"
        )
        assert result.agree_count == 1
        assert result.disagree_count == 1

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_empty_feedback_returns_zero_stats(self, mock_get_resource: MagicMock) -> None:
        """피드백 항목 0건 → agree_ratio=0.0, last_feedback_at=None."""
        from ai.search.feedback import aggregate_feedback_stats

        table_mock = _make_mock_table(query_items=[])
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        result = aggregate_feedback_stats("h-empty")

        assert result.total_count == 0
        assert result.agree_ratio == 0.0
        assert result.last_feedback_at is None

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_last_feedback_at_is_max_timestamp(self, mock_get_resource: MagicMock) -> None:
        """received_at 중 가장 최신 시각이 last_feedback_at 으로 설정돼야 한다."""
        from ai.search.feedback import aggregate_feedback_stats

        items = [
            _make_ddb_feedback_item(
                "FEEDBACK#dev-001#2026-05-01T10:00:00",
                "agree",
                received_at="2026-05-01T10:00:00+00:00",
            ),
            _make_ddb_feedback_item(
                "FEEDBACK#dev-002#2026-05-28T12:00:00",
                "agree",
                received_at="2026-05-28T12:00:00+00:00",
            ),
            _make_ddb_feedback_item(
                "FEEDBACK#dev-003#2026-05-15T08:00:00",
                "disagree",
                received_at="2026-05-15T08:00:00+00:00",
            ),
        ]
        table_mock = _make_mock_table(query_items=items)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        result = aggregate_feedback_stats("h-001")

        assert result.last_feedback_at is not None
        # 가장 최신 타임스탬프 = 2026-05-28T12:00:00
        assert result.last_feedback_at.year == 2026
        assert result.last_feedback_at.month == 5
        assert result.last_feedback_at.day == 28

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_correct_table_name_used(self, mock_get_resource: MagicMock) -> None:
        """DYNAMO_TABLE 환경변수 기본값 테이블이 사용돼야 한다."""
        from ai.search.feedback import aggregate_feedback_stats, _DYNAMO_TABLE

        table_mock = _make_mock_table(query_items=[])
        resource_mock = _make_mock_resource(table_mock)
        mock_get_resource.return_value = resource_mock

        aggregate_feedback_stats("h-001")

        # .Table(올바른_이름) 으로 호출됐는지 확인
        resource_mock.Table.assert_called_once_with(_DYNAMO_TABLE)

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_sk_begins_with_query_condition(self, mock_get_resource: MagicMock) -> None:
        """query KeyConditionExpression 에 SK begins_with FEEDBACK# 조건이 포함돼야 한다."""
        from ai.search.feedback import aggregate_feedback_stats

        table_mock = _make_mock_table(query_items=[])
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        aggregate_feedback_stats("h-001")

        # query 가 1회 이상 호출됐는지 확인
        assert table_mock.query.called

        # KeyConditionExpression 이 전달됐는지 확인 (표현식 내부 문자열 검사)
        call_kwargs = table_mock.query.call_args.kwargs
        expr = call_kwargs.get("KeyConditionExpression")
        assert expr is not None, "KeyConditionExpression 누락"

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_pagination_collects_all_items(self, mock_get_resource: MagicMock) -> None:
        """LastEvaluatedKey 가 있으면 다음 페이지를 계속 조회해야 한다."""
        from ai.search.feedback import aggregate_feedback_stats

        page1_items = [
            _make_ddb_feedback_item("FEEDBACK#dev-001#2026-05-28T10:00:00", "agree"),
        ]
        page2_items = [
            _make_ddb_feedback_item("FEEDBACK#dev-002#2026-05-28T11:00:00", "agree"),
        ]

        table_mock = MagicMock()
        # 첫 쿼리는 LastEvaluatedKey 포함
        table_mock.query.side_effect = [
            {"Items": page1_items, "LastEvaluatedKey": {"hospital_id": "h-001", "entity": "FEEDBACK#dev-001#ts"}},
            {"Items": page2_items},  # 두 번째 쿼리 — 종료
        ]
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        result = aggregate_feedback_stats("h-001")

        # 두 페이지 합산 → total=2
        assert result.total_count == 2
        assert table_mock.query.call_count == 2

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_returns_feedback_stats_model(self, mock_get_resource: MagicMock) -> None:
        """반환 타입이 FeedbackStats Pydantic 모델이어야 한다."""
        from ai.search.feedback import aggregate_feedback_stats

        table_mock = _make_mock_table(query_items=[])
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        result = aggregate_feedback_stats("h-001")

        assert isinstance(result, FeedbackStats)


# ---------------------------------------------------------------------------
# TestRecomputeConfidence
# ---------------------------------------------------------------------------

class TestRecomputeConfidence:
    """recompute_confidence V2 single-table SK=CLASSIFICATION 조회 검증."""

    def _make_classification_item(
        self,
        score: int | Decimal = 80,
        self_claim: int | Decimal = 25,
        vision: int | Decimal = 20,
        blog: int | Decimal = 20,
        reviews: int | Decimal = 25,
    ) -> dict:
        """CLASSIFICATION entity mock 딕셔너리 생성."""
        return {
            "hospital_id": "h-001",
            "entity": "CLASSIFICATION",
            "confidence": {
                "score": score,
                "signals": {
                    "self_claim": self_claim,
                    "vision": vision,
                    "blog": blog,
                    "reviews": reviews,
                },
            },
        }

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_base_score_80_disagree_majority_gets_penalized(
        self, mock_get_resource: MagicMock
    ) -> None:
        """base score=80, disagree 다수(≥70%) → 20점 감점 → score=60 이하."""
        from ai.search.feedback import recompute_confidence

        classification_item = self._make_classification_item(score=80)
        table_mock = _make_mock_table(query_items=[], get_item_response=classification_item)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        # 10건 중 8건 disagree (80%) → disagree_ratio=0.8 → penalty=20
        feedbacks = [
            _make_feedback_entry("disagree", feedback_id=f"fb-{i}", device_id=f"dev-{i}")
            for i in range(8)
        ] + [
            _make_feedback_entry("agree", feedback_id=f"fb-ag-{i}", device_id=f"dev-ag-{i}")
            for i in range(2)
        ]

        result = recompute_confidence("h-001", feedbacks)

        # base=80, penalty=20 → score=60
        assert result.score == 60, f"score={result.score} (expected 60)"
        assert isinstance(result, Confidence)

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_insufficient_feedback_raises_error(
        self, mock_get_resource: MagicMock
    ) -> None:
        """피드백 3건 미만이면 InsufficientFeedbackError 를 발생시켜야 한다."""
        from ai.search.feedback import recompute_confidence

        # DDB 호출이 아예 일어나면 안 됨 (임계값 미만 체크가 먼저)
        table_mock = _make_mock_table(query_items=[])
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        feedbacks_2 = [
            _make_feedback_entry("agree", feedback_id="fb-1", device_id="dev-1"),
            _make_feedback_entry("agree", feedback_id="fb-2", device_id="dev-2"),
        ]

        with pytest.raises(InsufficientFeedbackError):
            recompute_confidence("h-001", feedbacks_2)

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_insufficient_feedback_exactly_threshold_minus_one(
        self, mock_get_resource: MagicMock
    ) -> None:
        """정확히 _INSUFFICIENT_FEEDBACK_THRESHOLD - 1 건도 에러 발생."""
        from ai.search.feedback import recompute_confidence, _INSUFFICIENT_FEEDBACK_THRESHOLD

        table_mock = _make_mock_table(query_items=[])
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        feedbacks = [
            _make_feedback_entry("agree", feedback_id=f"fb-{i}", device_id=f"dev-{i}")
            for i in range(_INSUFFICIENT_FEEDBACK_THRESHOLD - 1)
        ]

        with pytest.raises(InsufficientFeedbackError):
            recompute_confidence("h-001", feedbacks)

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_high_agree_ratio_bonus_applied(
        self, mock_get_resource: MagicMock
    ) -> None:
        """agree_ratio >= 0.8 이면 보너스(최대 4점)가 더해져야 한다."""
        from ai.search.feedback import recompute_confidence

        classification_item = self._make_classification_item(score=70)
        table_mock = _make_mock_table(query_items=[], get_item_response=classification_item)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        # 5건 모두 agree (agree_ratio=1.0) → penalty=0, bonus=int(1.0*5)=5 → score=75
        feedbacks = [
            _make_feedback_entry("agree", feedback_id=f"fb-{i}", device_id=f"dev-{i}")
            for i in range(5)
        ]

        result = recompute_confidence("h-001", feedbacks)

        # base=70, penalty=0, bonus=int(1.0*5)=5 → score=75
        assert result.score == 75, f"score={result.score} (expected 75)"

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_classification_entity_key_used(
        self, mock_get_resource: MagicMock
    ) -> None:
        """get_item 호출 시 SK=CLASSIFICATION 키가 포함돼야 한다."""
        from ai.search.feedback import recompute_confidence, _SK_CLASSIFICATION

        classification_item = self._make_classification_item(score=75)
        table_mock = _make_mock_table(query_items=[], get_item_response=classification_item)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        feedbacks = [
            _make_feedback_entry("agree", feedback_id=f"fb-{i}", device_id=f"dev-{i}")
            for i in range(3)
        ]
        recompute_confidence("h-001", feedbacks)

        table_mock.get_item.assert_called_once()
        call_kwargs = table_mock.get_item.call_args.kwargs
        key = call_kwargs.get("Key", {})
        assert key.get("entity") == _SK_CLASSIFICATION, (
            f"SK={key.get('SK')!r} — CLASSIFICATION 이 아님"
        )
        assert key.get("hospital_id") == "h-001"

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_decimal_score_converted_safely(
        self, mock_get_resource: MagicMock
    ) -> None:
        """DynamoDB Decimal 타입 score 가 안전하게 int 로 변환돼야 한다."""
        from ai.search.feedback import recompute_confidence

        # DynamoDB 에서 숫자는 Decimal 로 옴
        classification_item = self._make_classification_item(
            score=Decimal("80"),
            self_claim=Decimal("25"),
            vision=Decimal("10"),
            blog=Decimal("20"),
            reviews=Decimal("25"),
        )
        table_mock = _make_mock_table(query_items=[], get_item_response=classification_item)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        feedbacks = [
            _make_feedback_entry("agree", feedback_id=f"fb-{i}", device_id=f"dev-{i}")
            for i in range(3)
        ]

        # Decimal 변환 중 TypeError / InvalidOperation 없이 완료돼야 함
        result = recompute_confidence("h-001", feedbacks)
        assert isinstance(result.score, int)

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_missing_classification_uses_defaults(
        self, mock_get_resource: MagicMock
    ) -> None:
        """CLASSIFICATION entity 가 없으면 기본값(score=70)으로 계산해야 한다."""
        from ai.search.feedback import recompute_confidence

        # get_item 이 빈 dict 반환 — 항목 없음
        table_mock = MagicMock()
        table_mock.get_item.return_value = {}
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        # 5건 agree (보너스 5) → base=70, penalty=0, bonus=5 → score=75
        feedbacks = [
            _make_feedback_entry("agree", feedback_id=f"fb-{i}", device_id=f"dev-{i}")
            for i in range(5)
        ]

        result = recompute_confidence("h-001", feedbacks)
        assert result.score == 75

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_disagree_30_percent_penalty_5(
        self, mock_get_resource: MagicMock
    ) -> None:
        """disagree_ratio >= 0.3 이면 penalty=5 적용."""
        from ai.search.feedback import recompute_confidence

        classification_item = self._make_classification_item(score=75)
        table_mock = _make_mock_table(query_items=[], get_item_response=classification_item)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        # 10건 중 3건 disagree (30%) → disagree_ratio=0.3 → penalty=5
        # agree_ratio=0.7 → bonus=0 (0.7 < 0.8)
        feedbacks = (
            [_make_feedback_entry("agree", feedback_id=f"fb-ag-{i}", device_id=f"dev-ag-{i}") for i in range(7)]
            + [_make_feedback_entry("disagree", feedback_id=f"fb-dis-{i}", device_id=f"dev-dis-{i}") for i in range(3)]
        )

        result = recompute_confidence("h-001", feedbacks)
        # base=75, penalty=5, bonus=0 → score=70
        assert result.score == 70, f"score={result.score} (expected 70)"

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_returns_confidence_model(
        self, mock_get_resource: MagicMock
    ) -> None:
        """반환 타입이 Confidence Pydantic 모델이어야 한다."""
        from ai.search.feedback import recompute_confidence

        classification_item = self._make_classification_item(score=70)
        table_mock = _make_mock_table(query_items=[], get_item_response=classification_item)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        feedbacks = [
            _make_feedback_entry("agree", feedback_id=f"fb-{i}", device_id=f"dev-{i}")
            for i in range(3)
        ]

        result = recompute_confidence("h-001", feedbacks)

        assert isinstance(result, Confidence)
        assert result.level in {"확실", "추정", "정보 부족"}
        assert 0 <= result.score <= 100

    @patch("ai.search.feedback.get_dynamodb_resource")
    def test_signal_contributions_reviews_boosted_by_agree(
        self, mock_get_resource: MagicMock
    ) -> None:
        """agree_ratio 가 높으면 reviews signal contribution 이 보정돼야 한다."""
        from ai.search.feedback import recompute_confidence

        classification_item = self._make_classification_item(score=70, reviews=25)
        table_mock = _make_mock_table(query_items=[], get_item_response=classification_item)
        mock_get_resource.return_value = _make_mock_resource(table_mock)

        # agree_ratio=1.0 → reviews += int(1.0 * 10) = 10 → reviews=35
        feedbacks = [
            _make_feedback_entry("agree", feedback_id=f"fb-{i}", device_id=f"dev-{i}")
            for i in range(5)
        ]

        result = recompute_confidence("h-001", feedbacks)
        assert result.signals.reviews == 35, (
            f"reviews signal={result.signals.reviews} (expected 35)"
        )
