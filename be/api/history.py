"""분류 변경 이력 API 라우터.

스펙: .claude/docs/API-FE-BE.md > 엔드포인트 > 3. 분류 변경 이력
응답 형식: {"data": [...]}
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from be.adapters.dynamo_adapter import DynamoAdapter

router = APIRouter(prefix="/api/hospitals", tags=["history"])
db = DynamoAdapter()


@router.get("/{hospital_id}/history")
def get_change_history(hospital_id: str, limit: int = Query(10, le=50)):
    """병원 분류 변경 이력 조회."""
    changes = db.load_recent_changes(hospital_id, limit=limit)
    return {
        "data": [c.model_dump() for c in changes],
    }
