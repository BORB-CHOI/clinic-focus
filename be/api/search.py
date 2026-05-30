"""검색 API 라우터.

스펙: .claude/docs/API-FE-BE.md > 엔드포인트 > 1. 검색
응답 형식: {"data": [...], "meta": {...}}

검색 경로 이원화:
- 자연어(q): AI 모듈 retrieve_hospital(KB Retrieve) → hospital_id 목록 → DDB join
- 위치(lat/lng): retrieve_hospital 이 KB 메타필터 bounding box + haversine 재계산
- 시군구만(sigungu): BE 가 DDB GSI 직접 조회 (KB 미경유)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from be.adapters.dynamo_adapter import DynamoAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])
db = DynamoAdapter()


def _hospital_card(hospital_id: str, *, distance_km=None, matched_focus=None) -> dict | None:
    """hospital_id → 검색 결과 카드. META + CLASSIFICATION + DESCRIPTION join.

    META 없으면 None(검색 결과에서 제외). 분류 전 병원은 분류 필드를 placeholder 로.
    """
    meta = db.load_hospital_meta(hospital_id)
    if not meta:
        return None
    classification = db.load_classification(hospital_id)
    description = db.load_description(hospital_id)
    return {
        "hospital_id": meta.hospital_id,
        "name": meta.name,
        "standard_specialty": classification.standard_specialty if classification else "",
        "primary_focus": classification.primary_focus if classification else [],
        "confidence": classification.confidence.model_dump() if classification else None,
        "location": meta.location.model_dump() if meta.location else None,
        "website_url": meta.contact.website_url if meta.contact else None,
        "one_line_summary": description.one_line_summary if description else "",
        "distance_km": distance_km,
        "matched_focus": matched_focus or [],
    }


@router.get("")
def search_hospitals(
    q: str | None = Query(None, description="자연어 검색 쿼리"),
    lat: float | None = Query(None),
    lng: float | None = Query(None),
    radius_km: float = Query(3.0, le=30),
    sido: str | None = Query(None),
    sigungu: str | None = Query(None),
    specialty: str | None = Query(None),
    min_confidence: int = Query(0, description="0=전체 노출(기본). >0 일 때만 신뢰도 하한 필터"),
    sort: str = Query("relevance"),
    limit: int = Query(20, le=50),
    offset: int = Query(0),
):
    """자연어 + 위치 복합 검색. q·lat/lng·sigungu 중 최소 하나 필수."""
    has_location = lat is not None and lng is not None
    # 명세(API-FE-BE.md 라인 356): q·lat/lng·sigungu 다 없으면 400 INVALID_PARAMETER
    if q is None and not has_location and not sigungu:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_PARAMETER",
                               "message": "q, lat/lng, sigungu 중 최소 하나는 필수입니다"}},
        )

    # 검색 모드 결정
    if q and has_location:
        search_mode = "natural+nearby"
    elif q:
        search_mode = "natural"
    elif has_location:
        search_mode = "nearby"
    else:
        search_mode = "category"

    results: list[dict] = []
    query_interpretation = None

    # --- 자연어/위치 경로: AI retrieve_hospital (KB Retrieve) ---
    if q or has_location:
        from shared.models import SearchQuery

        search_query = SearchQuery(
            query_text=q,
            lat=lat,
            lng=lng,
            radius_km=radius_km,
            sido=sido,
            sigungu=sigungu,
            specialty=specialty,
            min_confidence=min_confidence,
            sort=sort,  # type: ignore[arg-type]
            limit=limit,
        )
        from ai import retrieve_hospital
        from ai.core.exceptions import InvalidQueryError, KBRetrieveError

        try:
            search_results = retrieve_hospital(search_query)
        except InvalidQueryError as exc:
            # 쿼리 자체가 부적합(빈 텍스트 등) → 400 (클라이언트 책임)
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "INVALID_PARAMETER", "message": str(exc)}},
            )
        except (KBRetrieveError, Exception) as exc:
            # KB 호출 실패·자격증명 부재 등 시스템 측 → 502 (AI_SERVICE_ERROR)
            logger.warning("retrieve_hospital 실패: %s", exc)
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "AI_SERVICE_ERROR",
                                   "message": "자연어 검색 모듈 호출에 실패했습니다"}},
            )

        for sr in search_results:
            card = _hospital_card(
                sr.hospital_id,
                distance_km=sr.distance_km,
                matched_focus=sr.matched_focus,
            )
            if card:
                results.append(card)
            if sr.query_interpretation:
                query_interpretation = sr.query_interpretation

    # --- 시군구 단독(카테고리) 경로: DDB GSI 직접 ---
    elif sigungu:
        if specialty:
            metas = db.list_hospitals_by_sigungu_specialty(sigungu, specialty, limit=offset + limit)
        else:
            metas = db.list_hospitals_by_sigungu(sigungu)
        for meta in metas[offset:offset + limit]:
            card = _hospital_card(meta.hospital_id)
            if card:
                results.append(card)

    return {
        "data": results,
        "meta": {
            "total": len(results),
            "limit": limit,
            "offset": offset,
            "search_mode": search_mode,
            "query_interpretation": query_interpretation,
            "sort": sort,
        },
    }
