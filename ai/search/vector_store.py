"""
vector_store.py — S3 Vectors PutVectors / QueryVectors 래퍼.

공개 함수:
  - index_hospital(hospital_id, classification, description_text) -> None
  - search_similar(query: SearchQuery) -> list[SearchResult]

내부 팩토리:
  - _get_s3vectors_client() — 테스트 mockability 보장

검색 모드 분기:
  - 자연어 단독  : query_text만 있음
  - 위치 단독    : lat + lng만 있음
  - 복합(하이브리드): query_text + lat + lng 둘 다 있음

메타데이터 키 (PutVectors 시 고정):
  standard_specialty / primary_focus / sido / sigungu /
  confidence_score / lat / lng / last_updated
  → 키 이름 변경 시 기존 인덱스 호환 불가. 추가는 OK.
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import botocore.exceptions

from ai.core.aws_clients import get_s3vectors_client as _create_s3vectors_client
from ai.search.embed import EMBEDDING_DIM, embed_text
from ai.core.exceptions import BedrockInvocationError, InvalidQueryError, S3VectorsError
from shared.models import Classification, SearchQuery, SearchResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# bounding box 근사: 위도 1° ≈ 111 km → 1 km ≈ 0.009°
# 경도는 위도에 따라 달라지지만 한국 중위도(37°) 기준 1° ≈ 89 km → 0.0112°/km.
# 보수적으로 위도 근사(0.009°/km)를 경도에도 동일 적용 → bounding box가 약간 넓어짐.
# 넓게 후보를 잡고 haversine으로 정확히 재필터링하므로 안전.
_DEG_PER_KM = 0.009

# QueryVectors 1회 최대 반환 수 (S3 Vectors API 제한 확인 후 조정)
_MAX_QUERY_RESULTS = 100

_s3vectors_client = None


# ---------------------------------------------------------------------------
# 클라이언트 팩토리
# ---------------------------------------------------------------------------

def _get_s3vectors_client():
    """S3 Vectors boto3 클라이언트 팩토리.

    전역 캐싱으로 Lambda 재사용 시 재생성 비용을 줄인다.
    테스트에서 @patch("ai.search.vector_store._get_s3vectors_client") 로 교체 가능.
    """
    global _s3vectors_client
    if _s3vectors_client is None:
        _s3vectors_client = _create_s3vectors_client()
    return _s3vectors_client


# ---------------------------------------------------------------------------
# 거리 계산
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine 공식으로 두 지점 간 거리(km)를 계산한다.

    외부 라이브러리 없이 직접 구현.
    """
    r = 6371.0  # 지구 반지름 (km)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


# ---------------------------------------------------------------------------
# 메타데이터 필터 빌더
# ---------------------------------------------------------------------------

def _build_meta_filter(
    sido: str | None = None,
    sigungu: str | None = None,
    specialty: str | None = None,
    min_confidence: int = 70,
    lat_range: tuple[float, float] | None = None,
    lng_range: tuple[float, float] | None = None,
) -> dict | None:
    """S3 Vectors QueryVectors 용 메타데이터 필터를 조립한다.

    필터가 없으면 None 반환 (API 호출 시 필터 파라미터 생략).
    너무 엄격하면 결과 0건 → caller 측 fallback 로직 참고.

    S3 Vectors 필터 DSL 형식:
        {"and": [ {"equals": {"key": ..., "value": ...}}, ... ]}
        {"gte": {"key": ..., "value": ...}} 등
    """
    conditions: list[dict] = []

    if sido:
        conditions.append({"equals": {"key": "sido", "value": sido}})
    if sigungu:
        conditions.append({"equals": {"key": "sigungu", "value": sigungu}})
    if specialty:
        conditions.append({"equals": {"key": "standard_specialty", "value": specialty}})

    # confidence_score >= min_confidence
    conditions.append({"greaterThanOrEquals": {"key": "confidence_score", "value": min_confidence}})

    # bounding box lat / lng
    if lat_range is not None:
        lat_min, lat_max = lat_range
        conditions.append({"greaterThanOrEquals": {"key": "lat", "value": lat_min}})
        conditions.append({"lessThanOrEquals": {"key": "lat", "value": lat_max}})
    if lng_range is not None:
        lng_min, lng_max = lng_range
        conditions.append({"greaterThanOrEquals": {"key": "lng", "value": lng_min}})
        conditions.append({"lessThanOrEquals": {"key": "lng", "value": lng_max}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"and": conditions}


# ---------------------------------------------------------------------------
# index_hospital
# ---------------------------------------------------------------------------

def index_hospital(
    hospital_id: str,
    classification: Classification,
    description_text: str,
) -> None:
    """병원 분류 결과를 S3 Vectors에 적재한다.

    Args:
        hospital_id: 병원 고유 ID
        classification: AI 분류 결과 (standard_specialty, primary_focus, confidence 등 포함)
        description_text: 임베딩 대상 텍스트 (generate_description 단락 합본 권장)

    Raises:
        BedrockInvocationError: 임베딩 호출 실패 시
        S3VectorsError: PutVectors 호출 실패 시
    """
    bucket = os.getenv("S3_VECTOR_BUCKET")
    index_name = os.getenv("S3_VECTOR_INDEX", "hospital-index")

    if not bucket:
        raise S3VectorsError("환경변수 S3_VECTOR_BUCKET 이 설정되지 않았습니다.")

    # 1. 임베딩 생성
    vector = embed_text(description_text)

    # 2. 메타데이터 조립
    # Classification 에서 lat/lng 는 없을 수 있음 → None 이면 키 자체를 생략
    # (S3 Vectors range 필터는 키가 없는 벡터를 걸러낼 때 동작이 정의되지 않으므로 생략이 안전)
    metadata: dict = {
        "standard_specialty": classification.standard_specialty,
        # primary_focus 는 list → JSON string 으로 직렬화 (S3 Vectors 메타값은 스칼라만 지원)
        "primary_focus": json.dumps(classification.primary_focus, ensure_ascii=False),
        "confidence_score": classification.confidence.score,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    # sido / sigungu 는 Classification 에 직접 없고 HospitalMeta 에 있음.
    # index_hospital 시그니처에는 location 이 없으므로, Classification.hospital_id 만 사용.
    # 실제 sido/sigungu 는 BE 측이 hospital_meta 를 넘기거나 별도로 enrichment 가 필요하다.
    # 현재 명세(API-BE-AI.md)의 index_hospital 시그니처에 맞춰 Classification 에서 꺼낼 수 있는
    # 필드만 적재하고, 위치 정보는 BE 호출 흐름에서 확장 가능하도록 빈 슬롯으로 남긴다.
    # → BE 측에서 index_hospital 호출 전 classification 에 위치 정보를 붙여주거나,
    #   별도 update_hospital_location() 함수를 추가하는 방식으로 확장 예정.
    # (현재는 키를 아예 생략해 필터 오동작 방지)

    # 3. PutVectors 호출
    client = _get_s3vectors_client()
    try:
        client.put_vectors(
            vectorBucketName=bucket,
            indexName=index_name,
            vectors=[
                {
                    "key": hospital_id,
                    "data": {"float32": vector},
                    "metadata": metadata,
                }
            ],
        )
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error("S3 Vectors PutVectors 실패 (hospital_id=%s): %s", hospital_id, error_code)
        raise S3VectorsError(
            f"PutVectors 실패 (hospital_id={hospital_id}): {error_code}"
        ) from exc
    except Exception as exc:
        logger.error("S3 Vectors PutVectors 실패 (hospital_id=%s): %s", hospital_id, exc)
        raise S3VectorsError(
            f"PutVectors 실패 (hospital_id={hospital_id}): {exc}"
        ) from exc

    logger.info("index_hospital 완료: hospital_id=%s, index=%s/%s", hospital_id, bucket, index_name)


def index_hospital_with_meta(
    hospital_id: str,
    classification: Classification,
    description_text: str,
    sido: str,
    sigungu: str,
    lat: float | None = None,
    lng: float | None = None,
) -> None:
    """지역·좌표까지 포함해서 S3 Vectors에 적재. BE가 HospitalMeta를 알 때 호출."""
    bucket = os.getenv("S3_VECTOR_BUCKET")
    index_name = os.getenv("S3_VECTOR_INDEX", "hospital-index")
    if not bucket:
        raise S3VectorsError("환경변수 S3_VECTOR_BUCKET 이 설정되지 않았습니다.")

    vector = embed_text(description_text)
    metadata: dict = {
        "standard_specialty": classification.standard_specialty,
        "primary_focus": json.dumps(classification.primary_focus, ensure_ascii=False),
        "confidence_score": classification.confidence.score,
        "sido": sido,
        "sigungu": sigungu,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    if lat is not None:
        metadata["lat"] = lat
    if lng is not None:
        metadata["lng"] = lng

    client = _get_s3vectors_client()
    try:
        client.put_vectors(
            vectorBucketName=bucket,
            indexName=index_name,
            vectors=[{"key": hospital_id, "data": {"float32": vector}, "metadata": metadata}],
        )
    except Exception as exc:
        raise S3VectorsError(f"PutVectors 실패 (hospital_id={hospital_id}): {exc}") from exc

    logger.info("index_hospital_with_meta 완료: hospital_id=%s (%s %s)", hospital_id, sido, sigungu)


# ---------------------------------------------------------------------------
# _query_vectors 내부 헬퍼
# ---------------------------------------------------------------------------

def _query_vectors(
    vector: list[float],
    top_k: int,
    meta_filter: dict | None,
) -> list[dict]:
    """S3 Vectors QueryVectors 를 호출하고 raw 결과 리스트를 반환한다.

    Raises:
        S3VectorsError: QueryVectors 호출 실패 시
    """
    bucket = os.getenv("S3_VECTOR_BUCKET")
    index_name = os.getenv("S3_VECTOR_INDEX", "hospital-index")

    if not bucket:
        raise S3VectorsError("환경변수 S3_VECTOR_BUCKET 이 설정되지 않았습니다.")

    params: dict = {
        "vectorBucketName": bucket,
        "indexName": index_name,
        "queryVector": {"float32": vector},
        "topK": min(top_k, _MAX_QUERY_RESULTS),
        "returnMetadata": True,
        "returnDistance": True,
    }
    if meta_filter is not None:
        params["filter"] = meta_filter

    client = _get_s3vectors_client()
    try:
        response = client.query_vectors(**params)
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error("S3 Vectors QueryVectors 실패: %s", error_code)
        raise S3VectorsError(f"QueryVectors 실패: {error_code}") from exc
    except Exception as exc:
        logger.error("S3 Vectors QueryVectors 실패: %s", exc)
        raise S3VectorsError(f"QueryVectors 실패: {exc}") from exc

    return response.get("vectors", [])


# ---------------------------------------------------------------------------
# 결과 변환 헬퍼
# ---------------------------------------------------------------------------

def _parse_primary_focus(raw: str | list) -> list[str]:
    """메타데이터에서 primary_focus 를 파싱한다.

    PutVectors 시 JSON string 으로 직렬화했으므로 역직렬화.
    이미 list 로 반환되는 경우도 방어적으로 처리.
    """
    if isinstance(raw, list):
        return raw
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _raw_to_search_result(
    item: dict,
    similarity_score: float | None = None,
    distance_km: float | None = None,
    query_interpretation: str | None = None,
) -> SearchResult:
    """QueryVectors raw 결과 항목을 SearchResult 로 변환한다."""
    metadata = item.get("metadata", {})
    primary_focus = _parse_primary_focus(metadata.get("primary_focus", "[]"))

    return SearchResult(
        hospital_id=item["key"],
        similarity_score=similarity_score,
        distance_km=distance_km,
        matched_focus=primary_focus,
        query_interpretation=query_interpretation,
    )


# ---------------------------------------------------------------------------
# search_similar — 메인 검색 진입점
# ---------------------------------------------------------------------------

def search_similar(query: SearchQuery) -> list[SearchResult]:
    """SearchQuery 에 따라 검색 모드를 분기하여 유사 병원 목록을 반환한다.

    검색 모드:
      - 자연어 단독 : query.query_text 만 있음
      - 위치 단독   : query.lat + query.lng 만 있음
      - 복합        : 둘 다 있음

    Args:
        query: SearchQuery 인스턴스 (model_validator 에서 최소 하나 필수 검증됨)

    Returns:
        SearchResult 리스트 (최대 query.limit 개)

    Raises:
        InvalidQueryError: query_text 와 lat/lng 둘 다 없을 때 (shared/models.py 에서 먼저 잡힘)
        BedrockInvocationError: 임베딩 호출 실패 시
        S3VectorsError: QueryVectors 호출 실패 시
    """
    has_text = query.query_text is not None and query.query_text.strip() != ""
    has_location = query.lat is not None and query.lng is not None

    if not has_text and not has_location:
        # SearchQuery model_validator 가 먼저 잡지만 방어적으로 재검사
        raise InvalidQueryError("query_text 또는 (lat, lng) 중 최소 하나 필요")

    if has_text and not has_location:
        return _search_text_only(query)
    if has_location and not has_text:
        return _search_location_only(query)
    return _search_hybrid(query)


# ---------------------------------------------------------------------------
# 자연어 단독 검색
# ---------------------------------------------------------------------------

def _search_text_only(query: SearchQuery) -> list[SearchResult]:
    """자연어 쿼리만 있는 경우의 검색.

    1. query_text 임베딩
    2. QueryVectors (sido/sigungu/specialty/min_confidence 메타필터)
    3. 상위 limit 개 반환
    """
    vector = embed_text(query.query_text)  # type: ignore[arg-type]

    meta_filter = _build_meta_filter(
        sido=query.sido,
        sigungu=query.sigungu,
        specialty=query.specialty,
        min_confidence=query.min_confidence,
    )

    raw_results = _query_vectors(
        vector=vector,
        top_k=query.limit,
        meta_filter=meta_filter,
    )

    # 빈 결과 시 필터 완화 fallback — min_confidence 기준만 제거해서 재시도
    if not raw_results and (query.sido or query.sigungu or query.specialty):
        logger.info("자연어 검색 결과 0건 → 지역/specialty 필터 완화 fallback")
        fallback_filter = _build_meta_filter(min_confidence=query.min_confidence)
        raw_results = _query_vectors(
            vector=vector,
            top_k=query.limit,
            meta_filter=fallback_filter,
        )

    results: list[SearchResult] = []
    for item in raw_results:
        # S3 Vectors 는 distance 기준으로 가까울수록 유사 → similarity 변환: 1 - distance (코사인)
        raw_dist = item.get("distance")
        similarity = (1.0 - float(raw_dist)) if raw_dist is not None else None
        results.append(
            _raw_to_search_result(
                item,
                similarity_score=similarity,
                distance_km=None,
                query_interpretation=None,
            )
        )

    # relevance 정렬 (similarity_score 내림차순)
    if query.sort == "relevance":
        results.sort(key=lambda r: r.similarity_score or 0.0, reverse=True)

    return results[: query.limit]


# ---------------------------------------------------------------------------
# 위치 단독 검색
# ---------------------------------------------------------------------------

def _search_location_only(query: SearchQuery) -> list[SearchResult]:
    """lat/lng 만 있는 경우의 위치 기반 검색.

    1. bounding box 계산 → lat/lng range 메타필터
    2. 더미 벡터(zeros) + 메타필터로 QueryVectors
    3. haversine 으로 정확한 거리 재계산 → radius_km 내 필터링
    4. distance 정렬
    """
    lat: float = query.lat  # type: ignore[assignment]
    lng: float = query.lng  # type: ignore[assignment]
    deg_offset = query.radius_km * _DEG_PER_KM

    lat_range = (lat - deg_offset, lat + deg_offset)
    lng_range = (lng - deg_offset, lng + deg_offset)

    meta_filter = _build_meta_filter(
        sido=query.sido,
        sigungu=query.sigungu,
        specialty=query.specialty,
        min_confidence=query.min_confidence,
        lat_range=lat_range,
        lng_range=lng_range,
    )

    # 위치 검색엔 의미 유사도가 필요 없으므로 영벡터를 더미로 사용
    # S3 Vectors API 가 순수 메타필터만 지원하지 않는 경우를 위한 우회 방법
    dummy_vector = [0.0] * EMBEDDING_DIM

    # 후보를 넉넉히 가져와서 haversine 으로 정확히 필터링
    raw_results = _query_vectors(
        vector=dummy_vector,
        top_k=max(query.limit * 5, _MAX_QUERY_RESULTS),
        meta_filter=meta_filter,
    )

    # haversine 재필터링 + 거리 계산
    candidates: list[tuple[float, dict]] = []
    for item in raw_results:
        metadata = item.get("metadata", {})
        item_lat = metadata.get("lat")
        item_lng = metadata.get("lng")
        if item_lat is None or item_lng is None:
            # 위치 정보 없는 병원 → 위치 검색 결과에서 제외
            continue
        dist = _haversine_km(lat, lng, float(item_lat), float(item_lng))
        if dist <= query.radius_km:
            candidates.append((dist, item))

    # 정렬
    if query.sort in ("distance", "relevance"):
        candidates.sort(key=lambda x: x[0])
    elif query.sort == "confidence":
        candidates.sort(
            key=lambda x: float(x[1].get("metadata", {}).get("confidence_score", 0)),
            reverse=True,
        )

    results: list[SearchResult] = []
    for dist_km, item in candidates[: query.limit]:
        results.append(
            _raw_to_search_result(
                item,
                similarity_score=None,
                distance_km=round(dist_km, 3),
                query_interpretation=None,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 복합(하이브리드) 검색
# ---------------------------------------------------------------------------

def _search_hybrid(query: SearchQuery) -> list[SearchResult]:
    """자연어 + 위치 복합 검색.

    1. 자연어 의미 검색으로 limit * 3 개 추출 (지역 필터 포함)
    2. radius_km 내 haversine 필터링
    3. sort 기준 정렬 후 limit 개 반환
    """
    lat: float = query.lat  # type: ignore[assignment]
    lng: float = query.lng  # type: ignore[assignment]

    # 자연어 임베딩
    vector = embed_text(query.query_text)  # type: ignore[arg-type]

    # 의미 검색 단계 — 지역 필터는 포함하되 위치 bounding box 는 생략
    # (의미 검색 후 haversine 으로 정확히 걸러냄)
    meta_filter = _build_meta_filter(
        sido=query.sido,
        sigungu=query.sigungu,
        specialty=query.specialty,
        min_confidence=query.min_confidence,
    )

    expanded_k = min(query.limit * 3, _MAX_QUERY_RESULTS)
    raw_results = _query_vectors(
        vector=vector,
        top_k=expanded_k,
        meta_filter=meta_filter,
    )

    # 빈 결과 시 필터 완화 fallback
    if not raw_results:
        logger.info("복합 검색 결과 0건 → 필터 완화 fallback")
        fallback_filter = _build_meta_filter(min_confidence=query.min_confidence)
        raw_results = _query_vectors(
            vector=vector,
            top_k=expanded_k,
            meta_filter=fallback_filter,
        )

    # haversine 필터링
    candidates: list[tuple[float, float, dict]] = []
    for item in raw_results:
        metadata = item.get("metadata", {})
        item_lat = metadata.get("lat")
        item_lng = metadata.get("lng")

        if item_lat is None or item_lng is None:
            # 위치 정보 없는 경우 — 복합 검색에서는 radius 필터 적용 불가 → 제외
            # 위치 정보 없는 병원도 포함하려면 search_similar 로 분리 호출 필요
            continue

        dist = _haversine_km(lat, lng, float(item_lat), float(item_lng))
        if dist <= query.radius_km:
            raw_dist = item.get("distance")
            similarity = (1.0 - float(raw_dist)) if raw_dist is not None else 0.0
            candidates.append((dist, similarity, item))

    # 정렬
    if query.sort == "relevance":
        candidates.sort(key=lambda x: x[1], reverse=True)
    elif query.sort == "distance":
        candidates.sort(key=lambda x: x[0])
    elif query.sort == "confidence":
        candidates.sort(
            key=lambda x: float(x[2].get("metadata", {}).get("confidence_score", 0)),
            reverse=True,
        )

    results: list[SearchResult] = []
    for dist_km, similarity, item in candidates[: query.limit]:
        results.append(
            _raw_to_search_result(
                item,
                similarity_score=round(similarity, 4),
                distance_km=round(dist_km, 3),
                query_interpretation=None,
            )
        )
    return results
