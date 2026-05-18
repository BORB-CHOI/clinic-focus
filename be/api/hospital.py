"""병원 상세 API 라우터."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ai import aggregate_feedback_stats
from be.adapters.dynamo_adapter import DynamoAdapter

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])
db = DynamoAdapter()


@router.get("/{hospital_id}")
def get_hospital_detail(hospital_id: str):
    """
    병원 상세 페이지 — 9개 영역 데이터 반환.
    ① AI 통합 설명
    ② 핵심 진료 정보
    ③ 의료진 정보
    ④ 신뢰도·근거
    ⑤ 기본 운영 정보
    ⑥ 사용자 피드백
    ⑦ 분류 변경 이력
    ⑧ 관련 병원 추천
    ⑨ 메타 정보
    """
    meta = db.load_hospital_meta(hospital_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Hospital not found")

    classification = db.load_classification(hospital_id)
    description = db.load_description(hospital_id)
    services_and_doctors = db.load_services_and_doctors(hospital_id)
    related = db.load_related_hospitals(hospital_id)
    recent_changes = db.load_recent_changes(hospital_id, limit=2)

    # 피드백 통계
    feedback_stats = aggregate_feedback_stats(hospital_id)

    return {
        # ① AI 통합 설명
        "ai_description": description.model_dump() if description else None,
        # ② 핵심 진료 정보
        "classification": classification.model_dump() if classification else None,
        "services": services_and_doctors.services if services_and_doctors else [],
        "excluded_services": [s.model_dump() for s in services_and_doctors.excluded_services] if services_and_doctors else [],
        "equipment": [e.model_dump() for e in services_and_doctors.equipment] if services_and_doctors else [],
        "prices": [p.model_dump() for p in services_and_doctors.prices] if services_and_doctors else [],
        # ③ 의료진 정보
        "doctors": [d.model_dump() for d in services_and_doctors.doctors] if services_and_doctors else [],
        # ④ 신뢰도·근거
        "confidence": classification.confidence.model_dump() if classification else None,
        "detailed_signals": classification.detailed_signals.model_dump() if classification else None,
        # ⑤ 기본 운영 정보
        "meta": meta.model_dump(),
        # ⑥ 사용자 피드백
        "feedback_stats": feedback_stats.model_dump() if feedback_stats else None,
        # ⑦ 분류 변경 이력
        "recent_changes": [c.model_dump() for c in recent_changes],
        # ⑧ 관련 병원 추천
        "related_hospitals": [r.model_dump() for r in related],
        # ⑨ 메타 정보
        "data_updated_at": classification.classified_at.isoformat() if classification else None,
    }
