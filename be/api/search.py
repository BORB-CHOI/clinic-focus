"""검색 API 라우터."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ai import search_similar
from be.adapters.dynamo_adapter import DynamoAdapter
from shared.models import SearchQuery

router = APIRouter(prefix="/api/search", tags=["search"])
db = DynamoAdapter()


@router.get("")
def search_hospitals(
    q: str | None = Query(None, description="자연어 검색 쿼리"),
    lat: float | None = Query(None),
    lng: float | None = Query(None),
    radius_km: float = Query(3.0),
    sido: str | None = Query(None),
    sigungu: str | None = Query(None),
    specialty: str | None = Query(None),
    min_confidence: int = Query(70),
    sort: str = Query("relevance"),
    limit: int = Query(20, le=50),
):
    """자연어 + 위치 복합 검색."""
    query = SearchQuery(
        query_text=q,
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        sido=sido,
        sigungu=sigungu,
        specialty=specialty,
        min_confidence=min_confidence,
        sort=sort,
        limit=limit,
    )

    # AI 모듈로 검색
    ai_results = search_similar(query)

    # DynamoDB에서 병원 기본 정보 조인
    results = []
    for r in ai_results:
        meta = db.load_hospital_meta(r.hospital_id)
        classification = db.load_classification(r.hospital_id)
        desc = db.load_description(r.hospital_id)

        results.append({
            "hospital_id": r.hospital_id,
            "name": meta.name if meta else "",
            "address": meta.address if meta else "",
            "standard_specialty": classification.standard_specialty if classification else "",
            "primary_focus": classification.primary_focus if classification else [],
            "confidence": classification.confidence.model_dump() if classification else None,
            "one_line_summary": desc.one_line_summary if desc else "",
            "similarity_score": r.similarity_score,
            "distance_km": r.distance_km,
            "matched_focus": r.matched_focus,
            "query_interpretation": r.query_interpretation,
        })

    return {"results": results, "total": len(results)}


@router.get("/nearby")
def search_nearby(
    lat: float = Query(..., description="사용자 위도"),
    lng: float = Query(..., description="사용자 경도"),
    radius_km: float = Query(3.0),
    specialty: str | None = Query(None),
    min_confidence: int = Query(70),
    sort: str = Query("distance"),
    limit: int = Query(20, le=50),
):
    """위치 기반 내 근처 검색."""
    query = SearchQuery(
        lat=lat,
        lng=lng,
        radius_km=radius_km,
        specialty=specialty,
        min_confidence=min_confidence,
        sort=sort,
        limit=limit,
    )

    ai_results = search_similar(query)

    results = []
    for r in ai_results:
        meta = db.load_hospital_meta(r.hospital_id)
        classification = db.load_classification(r.hospital_id)
        desc = db.load_description(r.hospital_id)

        results.append({
            "hospital_id": r.hospital_id,
            "name": meta.name if meta else "",
            "address": meta.address if meta else "",
            "standard_specialty": classification.standard_specialty if classification else "",
            "primary_focus": classification.primary_focus if classification else [],
            "confidence": classification.confidence.model_dump() if classification else None,
            "one_line_summary": desc.one_line_summary if desc else "",
            "distance_km": r.distance_km,
            "location": meta.location.model_dump() if meta and meta.location else None,
        })

    return {"results": results, "total": len(results)}
