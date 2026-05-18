"""피드백 검증·처리 로직."""

from __future__ import annotations

from shared.models import FeedbackEntry, FeedbackStats

# 신뢰도 재계산 트리거 임계치
RECOMPUTE_THRESHOLD = 10  # 피드백 N건 이상 누적 시


def should_recompute(feedback_list: list[FeedbackEntry]) -> bool:
    """피드백 누적이 재계산 임계치를 넘었는지."""
    return len(feedback_list) >= RECOMPUTE_THRESHOLD


def compute_feedback_stats(feedback_list: list[FeedbackEntry]) -> FeedbackStats:
    """피드백 리스트에서 통계 계산."""
    if not feedback_list:
        return FeedbackStats()

    agree = sum(1 for f in feedback_list if f.verdict == "agree")
    disagree = sum(1 for f in feedback_list if f.verdict == "disagree")
    total = agree + disagree

    sorted_by_time = sorted(feedback_list, key=lambda f: f.received_at, reverse=True)

    return FeedbackStats(
        total_count=total,
        agree_count=agree,
        disagree_count=disagree,
        agree_ratio=round(agree / total, 3) if total > 0 else 0.0,
        last_feedback_at=sorted_by_time[0].received_at if sorted_by_time else None,
    )
