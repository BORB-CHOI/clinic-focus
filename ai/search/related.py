import math

from shared.models import ExcludedService, Location, RelatedHospital, SearchQuery, SearchResult


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_related_hospitals(
    hospital_id: str,
    location: Location,
    primary_focus: list[str],
    excluded_services: list[ExcludedService],
    limit: int = 5,
) -> list[RelatedHospital]:
    """상세 페이지 영역 ⑧: 같은 주력 + 빈자리 보완 병원 추천.

    ⚠️ 부작용: fills_gap 매칭 시 입력 ``excluded_services`` 의 각 항목
    ``alternative_hospital_ids`` 를 **in-place 로 채운다**(영역 ② ↔ ⑧ 연결).
    중복은 막지만, 같은 ExcludedService 객체를 여러 번 넘기면 누적되므로 호출자는
    1회 분류 흐름에서 새로 만든 객체를 넘길 것.
    """
    from ai.search.kb_store import retrieve_hospital

    results: list[RelatedHospital] = []

    # --- same_focus 추천 ---
    # primary_focus 가 비면 query_text 가 빈 문자열이 돼 KB Retrieve 가 InvalidQueryError
    # 를 던진다(빈 쿼리 불가). 그러면 병원 전체 파이프라인이 실패하므로, 주력 분야가
    # 없는 병원(=신호 부족)은 같은-주력 추천을 **건너뛰고** 빈 결과로 진행한다.
    focus_query = " ".join(primary_focus).strip()
    same_focus_raw: list[SearchResult] = []
    if focus_query:
        if location.lat and location.lng:
            query = SearchQuery(
                query_text=focus_query,
                lat=location.lat,
                lng=location.lng,
                radius_km=3.0,
                min_confidence=70,
                sort="relevance",
                limit=limit * 2,
            )
        else:
            query = SearchQuery(
                query_text=focus_query,
                sido=location.sido,
                sigungu=location.sigungu,
                min_confidence=70,
                sort="relevance",
                limit=limit * 2,
            )
        same_focus_raw = retrieve_hospital(query)
    for r in same_focus_raw:
        if r.hospital_id == hospital_id:
            continue
        dist = None
        if location.lat and location.lng and r.distance_km is not None:
            dist = r.distance_km
        results.append(RelatedHospital(
            hospital_id=r.hospital_id,
            name="",  # BE가 DynamoDB에서 조인
            primary_focus=r.matched_focus,
            similarity_score=r.similarity_score or 0.0,
            recommendation_type="same_focus",
            distance_km=dist,
        ))
        if len(results) >= limit - 2:
            break

    # --- fills_gap 추천 ---
    gap_limit = limit - len(results)
    for excluded in excluded_services[:gap_limit]:
        if not (excluded.name or "").strip():
            continue  # 빈 분야명은 KB Retrieve 빈 쿼리 에러를 유발하므로 건너뜀
        if location.lat and location.lng:
            gap_query = SearchQuery(
                query_text=excluded.name,
                lat=location.lat,
                lng=location.lng,
                radius_km=5.0,
                min_confidence=70,
                sort="relevance",
                limit=3,
            )
        else:
            gap_query = SearchQuery(
                query_text=excluded.name,
                sido=location.sido,
                sigungu=location.sigungu,
                min_confidence=70,
                sort="relevance",
                limit=3,
            )
        gap_raw = retrieve_hospital(gap_query)
        for r in gap_raw:
            if r.hospital_id == hospital_id:
                continue
            results.append(RelatedHospital(
                hospital_id=r.hospital_id,
                name="",
                primary_focus=r.matched_focus,
                similarity_score=r.similarity_score or 0.0,
                recommendation_type="fills_gap",
                distance_km=r.distance_km,
            ))
            # 영역 ⑧ 연결 — 이 excluded 분야의 대안 병원 ID 를 역으로 채움 (in-place).
            # 호출자가 같은 excluded_services 를 SERVICES entity 에 저장하면 alt_ids 가 박힌다.
            if r.hospital_id not in excluded.alternative_hospital_ids:
                excluded.alternative_hospital_ids.append(r.hospital_id)
            break

    return results[:limit]
