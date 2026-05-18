"""피드백 API 라우터."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai import recompute_confidence
from be.adapters.dynamo_adapter import DynamoAdapter
from be.core.feedback import compute_feedback_stats, should_recompute
from shared.models import FeedbackEntry

router = APIRouter(prefix="/api/feedback", tags=["feedback"])
db = DynamoAdapter()


class FeedbackRequest(BaseModel):
    hospital_id: str
    device_id: str
    primary_focus: str
    verdict: str  # "agree" | "disagree"


@router.post("")
def submit_feedback(req: FeedbackRequest):
    """1-tap 피드백 제출."""
    # 중복 체크
    if db.check_duplicate_feedback(req.hospital_id, req.device_id):
        raise HTTPException(status_code=409, detail="이미 피드백을 제출했습니다.")

    # 피드백 저장
    entry = FeedbackEntry(
        feedback_id=str(uuid.uuid4()),
        hospital_id=req.hospital_id,
        device_id=req.device_id,
        primary_focus=req.primary_focus,
        verdict=req.verdict,
        received_at=datetime.utcnow(),
    )
    db.save_feedback(entry)

    # 임계치 초과 시 신뢰도 재계산
    all_feedback = db.get_feedback_for_hospital(req.hospital_id)
    if should_recompute(all_feedback):
        try:
            new_confidence = recompute_confidence(req.hospital_id, all_feedback)
            # Classification 업데이트
            classification = db.load_classification(req.hospital_id)
            if classification:
                classification.confidence = new_confidence
                db.save_classification(classification)
        except Exception:
            pass  # 재계산 실패해도 피드백 저장은 성공

    return {"status": "saved", "feedback_id": entry.feedback_id}


@router.get("/{hospital_id}/stats")
def get_feedback_stats(hospital_id: str):
    """병원별 피드백 통계 조회."""
    feedback_list = db.get_feedback_for_hospital(hospital_id)
    stats = compute_feedback_stats(feedback_list)
    return stats.model_dump()
