"""검색 API 라우터.

스펙: .claude/docs/API-FE-BE.md > 엔드포인트 > 1. 검색
응답 형식: {"data": [...], "meta": {...}}

검색 경로 이원화:
- 자연어(q): AI 모듈 retrieve_hospital(KB Retrieve) → limit=FETCH_CAP 으로 전체 받아 BE 슬라이스
- 위치(lat/lng): retrieve_hospital 이 KB 메타필터 bounding box + haversine 재계산
- 시군구만(sigungu): BE 가 DDB GSI 직접 조회 (KB 미경유), 경량 처리 후 슬라이스만 하이드레이트

보조정렬 규칙 (2·3순위 결정적):
- relevance(NL): 유사도 desc → confidence_score desc → name asc
- confidence: confidence_score desc → 유사도 desc → name asc
- distance(위치必): 거리 asc → confidence_score desc → name asc
- 카테고리(q·위치 없음): confidence_score desc → name asc (relevance/distance 무의미)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from be.adapters.dynamo_adapter import DynamoAdapter
from shared.etc_category import display_specialty

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])
db = DynamoAdapter()

# AI retrieve_hospital 에 전달할 상한 — 전체를 한 번에 받아 BE가 페이지 슬라이스한다.
FETCH_CAP = 100


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
        # 파생 표시 카테고리: standard_specialty='기타'면 primary_focus 로 의미있는 하위
        # 카테고리(미용/모발·탈모/통증·근골격/수면/정신…) 도출. FE 가 '기타' 대신 노출.
        "etc_subcategory": (
            display_specialty(classification.standard_specialty, classification.primary_focus)
            if classification else ""
        ),
        "primary_focus": classification.primary_focus if classification else [],
        "confidence": classification.confidence.model_dump() if classification else None,
        "location": meta.location.model_dump() if meta.location else None,
        "website_url": meta.contact.website_url if meta.contact else None,
        "one_line_summary": description.one_line_summary if description else "",
        "distance_km": distance_km,
        "matched_focus": matched_focus or [],
    }


def _sort_nl_results(
    items: list[dict],
    sort: str,
    *,
    score_map: dict[str, float | None] | None = None,
) -> list[dict]:
    """자연어/위치 결과를 보조정렬 규칙에 따라 정렬.

    score_map: hospital_id → similarity_score (NL 경로에서만 유의미).
    카드의 confidence 는 dict 형태 {"score": N, ...} 이거나 None.
    """
    score_map = score_map or {}

    def _confidence(card: dict) -> float:
        conf = card.get("confidence")
        if isinstance(conf, dict):
            return float(conf.get("score", 0))
        return 0.0

    def _sim(card: dict) -> float:
        return float(score_map.get(card["hospital_id"]) or 0.0)

    def _dist(card: dict) -> float:
        d = card.get("distance_km")
        return float(d) if d is not None else 1e9

    def _name(card: dict) -> str:
        return card.get("name", "")

    if sort == "confidence":
        items.sort(key=lambda c: (-_confidence(c), -_sim(c), _name(c)))
    elif sort == "distance":
        items.sort(key=lambda c: (_dist(c), -_confidence(c), _name(c)))
    else:
        # relevance(기본): retrieve_hospital 이 이미 '주력 강도'(언급 빈도 + primary_focus
        # 일치 + 코사인)로 정렬해 돌려준다. 여기서 similarity(코사인) 로 재정렬하면 그 주력
        # 랭킹을 덮어써 버리므로(코사인만으론 주력이 안 잡힘), 들어온 순서를 그대로 보존한다.
        pass

    return items


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
    limit: int = Query(20, le=100),  # 상향: le=50 → le=100
    offset: int = Query(0),
):
    """자연어 + 위치 복합 검색. q·lat/lng·sigungu 중 최소 하나 필수.

    meta.total = 필터 후 진짜 전체 매칭 수(페이지 크기 아님).
    has_more = offset+limit < total.
    """
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

    # 응답에 포함할 위치 메타 (위치검색일 때만 채움)
    center_meta: dict | None = None
    radius_meta: float | None = None
    if has_location:
        center_meta = {"lat": lat, "lng": lng}
        radius_meta = radius_km

    all_cards: list[dict] = []
    query_interpretation = None

    # --- 자연어/위치 경로: AI retrieve_hospital (KB Retrieve) ---
    if q or has_location:
        from shared.models import SearchQuery

        # FETCH_CAP 으로 호출 — retrieve_hospital 이 이미 min-sim/정렬 처리된 전체를 돌려줌.
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
            limit=FETCH_CAP,
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

        # similarity_score 맵 — 보조정렬에서 2순위 tie-breaker 로 사용
        score_map: dict[str, float | None] = {}

        for sr in search_results:
            card = _hospital_card(
                sr.hospital_id,
                distance_km=sr.distance_km,
                matched_focus=sr.matched_focus,
            )
            if card:
                score_map[sr.hospital_id] = sr.similarity_score
                all_cards.append(card)
            if sr.query_interpretation:
                query_interpretation = sr.query_interpretation

        # 보조정렬 적용 (retrieve_hospital 이 1순위 정렬 해왔지만 2·3순위 보강)
        all_cards = _sort_nl_results(all_cards, sort, score_map=score_map)

    # --- 시군구 단독(카테고리) 경로: DDB GSI 직접 (경량 처리) ---
    elif sigungu:
        # 1) 경량 META 목록 확보 (hospital_id·name·confidence_score·standard_specialty 만)
        if specialty:
            light_items = db.list_hospitals_by_sigungu_specialty_light(sigungu, specialty)
        else:
            light_items = db.list_hospitals_by_sigungu_light(sigungu)

        # 2) min_confidence 필터 (META.confidence_score 로 슬라이스 전 적용)
        if min_confidence > 0:
            light_items = [
                it for it in light_items
                if float(it.get("confidence_score") or 0) >= min_confidence
            ]

        # 3) 카테고리 정렬: confidence_score desc → name asc (relevance/distance 무의미)
        light_items.sort(
            key=lambda it: (-float(it.get("confidence_score") or 0), it.get("name", ""))
        )

        total = len(light_items)

        # 4) 페이지 슬라이스 후 그 구간만 풀 하이드레이트 (_hospital_card = DDB 3회)
        page_slice = light_items[offset: offset + limit]
        for it in page_slice:
            card = _hospital_card(it["hospital_id"])
            if card:
                all_cards.append(card)

        # 카테고리 경로는 total 을 미리 계산했으므로 별도 처리
        return {
            "data": all_cards,
            "meta": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
                "search_mode": search_mode,
                "query_interpretation": None,
                "center": None,
                "radius_km": None,
                "sort": sort,
            },
        }

    # NL/위치 경로: total = 전체 카드 수, data = 슬라이스
    total = len(all_cards)
    page_data = all_cards[offset: offset + limit]

    return {
        "data": page_data,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
            "search_mode": search_mode,
            "query_interpretation": query_interpretation,
            "center": center_meta,
            "radius_km": radius_meta,
            "sort": sort,
        },
    }
