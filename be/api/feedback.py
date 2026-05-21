"""피드백 API 라우터.

스펙: .claude/docs/API-FE-BE.md > 엔드포인트 > 4. 피드백 제출
응답 형식:
  성공 201: {"data": {"feedback_id": "...", "received_at": "..."}}
  중복 409: {"error": {"code": "DUPLICATE_FEEDBACK", "message": "..."}}
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

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


@router.post("", status_code=201)
def submit_feedback(req: FeedbackRequest):
    """1-tap 피드백 제출. 익명 + device_id 기반 중복 방지."""
    # 중복 체크
    if db.check_duplicate_feedback(req.hospital_id, req.device_id):
        return {
            "error": {
                "code": "DUPLICATE_FEEDBACK",
                "message": "이 디바이스에서 해당 병원에 이미 피드백을 제출했습니다",
            }
        }

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

    # 임계치 초과 시 신뢰도 재계산 (AI 모듈 연동 후 활성화)
    # all_feedback = db.get_feedback_for_hospital(req.hospital_id)
    # if should_recompute(all_feedback):
    #     new_confidence = recompute_confidence(req.hospital_id, all_feedback)
    #     ...

    return {
        "data": {
            "feedback_id": entry.feedback_id,
            "received_at": entry.received_at.isoformat() + "Z",
        }
    }


@router.get("/{hospital_id}/stats")
def get_feedback_stats(hospital_id: str):
    """병원별 피드백 통계 조회."""
    feedback_list = db.get_feedback_for_hospital(hospital_id)
    stats = compute_feedback_stats(feedback_list)
    return {"data": stats.model_dump()}
