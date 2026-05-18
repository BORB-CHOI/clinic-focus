"""피드백 로직 단위 테스트."""

from datetime import datetime

from be.core.feedback import compute_feedback_stats, should_recompute
from shared.models import FeedbackEntry


def _make_feedback(verdict: str, idx: int = 0) -> FeedbackEntry:
    return FeedbackEntry(
        feedback_id=f"fb_{idx}",
        hospital_id="h_001",
        device_id=f"device_{idx}",
        primary_focus="일반 진료",
        verdict=verdict,
        received_at=datetime(2026, 5, 1, 10, idx),
    )


def test_compute_stats_empty():
    stats = compute_feedback_stats([])
    assert stats.total_count == 0
    assert stats.agree_ratio == 0.0


def test_compute_stats_mixed():
    entries = [
        _make_feedback("agree", 0),
        _make_feedback("agree", 1),
        _make_feedback("agree", 2),
        _make_feedback("disagree", 3),
    ]
    stats = compute_feedback_stats(entries)
    assert stats.total_count == 4
    assert stats.agree_count == 3
    assert stats.disagree_count == 1
    assert stats.agree_ratio == 0.75


def test_should_recompute_below_threshold():
    entries = [_make_feedback("agree", i) for i in range(5)]
    assert should_recompute(entries) is False


def test_should_recompute_above_threshold():
    entries = [_make_feedback("agree", i) for i in range(10)]
    assert should_recompute(entries) is True
