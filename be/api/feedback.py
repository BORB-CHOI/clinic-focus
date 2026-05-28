"""피드백 API 라우터.

스펙: .claude/docs/API-FE-BE.md > 엔드포인트 > 4. 피드백 제출
응답 형식:
  성공 201: {"data": {"feedback_id": "...", "received_at": "..."}}
  중복 409: {"error": {"code": "DUPLICATE_FEEDBACK", "message": "..."}}
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from be.adapters.dynamo_adapter import DynamoAdapter
from be.core.feedback import compute_feedback_stats, should_recompute
from shared.models import FeedbackEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])
db = DynamoAdapter()


class FeedbackRequest(BaseModel):
    hospital_id: str
    device_id: str
    primary_focus: str
    verdict: Literal["agree", "disagree"]  # 잘못된 값은 FastAPI 가 422 (명세 INVALID_PARAMETER)


def _maybe_recompute_confidence(hospital_id: str) -> None:
    """피드백 누적이 임계 도달 시 신뢰도 재계산 → CLASSIFICATION 의 confidence 갱신.

    분류(primary_focus·standard_specialty)는 유지하고 confidence 만 교체한다.
    AI 모듈/분류 부재·피드백 부족 등은 조용히 스킵(피드백 제출 자체는 성공시킨다).
    """
    from ai.core.exceptions import InsufficientFeedbackError

    try:
        all_feedback = db.get_feedback_for_hospital(hospital_id)
        if not should_recompute(all_feedback):
            return
        classification = db.load_classification(hospital_id)
        if classification is None:
            return  # 미분류 병원 — 정상 스킵

        from ai import recompute_confidence

        new_confidence = recompute_confidence(hospital_id, all_feedback)
        classification.confidence = new_confidence
        db.save_classification(classification)
        logger.info(
            "신뢰도 재계산 반영: hospital_id=%s score=%d level=%s",
            hospital_id, new_confidence.score, new_confidence.level,
        )
    except InsufficientFeedbackError:
        # 피드백 통계 미달 — 예상된 정상 흐름, 조용히 스킵
        return
    except Exception:
        # 예상 외 실패 — 스택 추적 남기되 피드백 제출(201)은 막지 않음 (graceful)
        logger.exception("신뢰도 재계산 예상 외 실패: hospital_id=%s", hospital_id)


@router.post("", status_code=201)
def submit_feedback(req: FeedbackRequest):
    """1-tap 피드백 제출. 익명 + device_id 기반 중복 방지."""
    # 중복 체크
    if db.check_duplicate_feedback(req.hospital_id, req.device_id):
        return JSONResponse(
            status_code=409,
            content={"error": {"code": "DUPLICATE_FEEDBACK", "message": "이 디바이스에서 해당 병원에 이미 피드백을 제출했습니다"}},
        )

    # 피드백 저장
    entry = FeedbackEntry(
        feedback_id=str(uuid.uuid4()),
        hospital_id=req.hospital_id,
        device_id=req.device_id,
        primary_focus=req.primary_focus,
        verdict=req.verdict,
        received_at=datetime.now(tz=timezone.utc),
    )
    db.save_feedback(entry)

    # 임계치 초과 시 신뢰도 재계산 — EventBridge 안 쓰니 inline (PoC).
    # 재계산된 confidence 만 기존 CLASSIFICATION 에 반영 (분류 자체는 유지).
    _maybe_recompute_confidence(req.hospital_id)

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
