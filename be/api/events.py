"""검색 이벤트 API 라우터 — 데이터 해자 핵심.

사용자가 검색 결과에서 병원을 노출(impression)·클릭(click)·선택(select)할 때
FE가 호출한다. 익명 session_id 기반이라 개인정보 없음.

저장 구조:
  PK = hospital_id
  SK = EVENT#{type}#{ISO-timestamp}

집계는 실시간이 아닌 be/scripts/compute_event_scores.py 가 주기적으로 수행.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from be.adapters.dynamo_adapter import DynamoAdapter
from shared.models import SearchEvent

router = APIRouter(prefix="/api/events", tags=["events"])
db = DynamoAdapter()


class SearchEventRequest(BaseModel):
    event_type: Literal["impression", "click", "select"]
    session_id: str
    hospital_id: str
    query: str | None = None
    position: int | None = None


@router.post("", status_code=201)
def record_event(req: SearchEventRequest):
    """검색 이벤트 1건 저장. 실패해도 UX에 영향 없어야 하므로 에러를 조용히 처리."""
    event = SearchEvent(
        event_id=str(uuid.uuid4()),
        event_type=req.event_type,
        session_id=req.session_id,
        hospital_id=req.hospital_id,
        query=req.query,
        position=req.position,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.save_search_event(event)
    return {
        "data": {
            "event_id": event.event_id,
            "received_at": event.created_at.isoformat(),
        }
    }
