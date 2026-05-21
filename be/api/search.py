"""검색 API 라우터.

스펙: .claude/docs/API-FE-BE.md > 엔드포인트 > 1. 검색
응답 형식: {"data": [...], "meta": {...}}
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from be.adapters.dynamo_adapter import DynamoAdapter

router = APIRouter(prefix="/api/search", tags=["search"])
db = DynamoAdapter()


@router.get("")
def search_hospitals(
    q: str | None = Query(None, description="자연어 검색 쿼리"),
    lat: float | None = Query(None),
    lng: float | None = Query(None),
    radius_km: float = Query(3.0, le=30),
    sido: str | None = Query(None),
    sigungu: str | None = Query(None),
    specialty: str | None = Query(None),
    min_confidence: int = Query(70),
    sort: str = Query("relevance"),
    limit: int = Query(20, le=50),
    offset: int = Query(0),
):
    """자연어 + 위치 복합 검색.

    q와 lat/lng 중 최소 하나는 필수.
    """
    # 파라미터 검증
    if q is None and (lat is None or lng is None):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "INVALID_PARAMETER", "message": "q 또는 lat/lng 중 최소 하나는 필수입니다"}},
        )

    # 검색 모드 결정
    if q and lat is not None and lng is not None:
        search_mode = "natural+nearby"
    elif q:
        search_mode = "natural"
    else:
        search_mode = "nearby"

    # TODO: AI 모듈 search_similar 연동 (비성님 파트 완성 후)
    # 현재는 DynamoDB에서 시군구 기반 조회로 대체
    if q and not sigungu:
        return JSONResponse(
            status_code=200,
            content={
                "data": [],
                "meta": {
                    "total": 0,
                    "limit": limit,
                    "offset": offset,
                    "search_mode": search_mode,
                    "query_interpretation": None,
                    "sort": sort,
                    "note": "자연어 검색은 AI 모듈 연동 후 지원됩니다. sigungu 파라미터로 지역 검색을 먼저 사용하세요.",
                },
            },
        )

    results = []

    if sigungu:
        hospitals = db.list_hospitals_by_sigungu(sigungu)
        for meta in hospitals[offset:offset + limit]:
            results.append({
                "hospital_id": meta.hospital_id,
                "name": meta.name,
                "standard_specialty": "",  # 분류 전
                "primary_focus": [],  # 분류 전
                "confidence": None,  # 분류 전
                "location": meta.location.model_dump() if meta.location else None,
                "website_url": meta.contact.website_url,
                "one_line_summary": "",  # AI 설명 생성 전
                "distance_km": None,
            })

    return {
        "data": results,
        "meta": {
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "search_mode": search_mode,
            "query_interpretation": None,
            "sort": sort,
        },
    }
