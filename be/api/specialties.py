"""진료과목 목록 API 라우터.

스펙: 공유 계약 §B — GET /api/specialties?sigungu=강남구
응답: {"data": [{"specialty": str, "count": int}, ...], "meta": {...}}

분류 완료된(sigungu_specialty GSI 등록) 병원만 집계한다.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from be.adapters.dynamo_adapter import DynamoAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/specialties", tags=["specialties"])
db = DynamoAdapter()


@router.get("")
def list_specialties(
    sigungu: str = Query(..., description="시군구 이름. 예: 강남구"),
):
    """시군구 내 진료과목별 분류완료 병원 수를 반환한다.

    카테고리 검색(진료과목 브라우즈) 화면의 칩 렌더링에 사용.
    분류 전 병원은 집계에서 제외된다(sigungu_specialty GSI 미등록).
    """
    if not sigungu or not sigungu.strip():
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_PARAMETER", "message": "sigungu 는 필수입니다"}},
        )

    try:
        specialty_list, total_hospitals = db.list_specialty_counts(sigungu.strip())
    except Exception as exc:
        logger.warning("list_specialty_counts 실패 sigungu=%s: %s", sigungu, exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "진료과목 집계 중 오류가 발생했습니다"}},
        )

    return {
        "data": specialty_list,
        "meta": {
            "sigungu": sigungu.strip(),
            "total_hospitals": total_hospitals,
            "total_specialties": len(specialty_list),
        },
    }
