"""계층형 카테고리 트리 API 라우터.

GET /api/categories?sigungu=강남구
응답: {"data": [{key, origin, count, sub:[{label,count}...]}, ...], "meta": {...}}

- L1(key) = display_category. 표준 진료과(피부과·치과…) + '기타'에서 해체·승격된 의미
  버킷(미용·모발·탈모·통증·근골격…). origin 으로 둘을 구분('specialty' | 'etc').
- L2(sub) = primary_focus 세부 시술·증상 태그 (taxonomy.py 기반), count 내림차순.
- 분류 완료(display_category 보유) 병원만 집계. count 내림차순 정렬.

둘러보기 랜딩에서 1단 진료과 그리드가 빈약해 보이던 문제(+ '기타' 덩어리)를 2단
계층(진료과/의미버킷 → 세부 시술)으로 해소. 닥터나우/굿닥/모두닥식 2단 필터 패턴.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from be.adapters.dynamo_adapter import DynamoAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/categories", tags=["categories"])
db = DynamoAdapter()


@router.get("")
def list_categories(
    sigungu: str = Query(..., description="시군구 이름. 예: 강남구"),
):
    """시군구 내 계층형 카테고리 트리(L1 분야 → L2 세부 시술)를 반환한다."""
    if not sigungu or not sigungu.strip():
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "INVALID_PARAMETER", "message": "sigungu 는 필수입니다"}},
        )

    try:
        tree, total_hospitals = db.list_category_tree(sigungu.strip())
    except Exception as exc:
        logger.warning("list_category_tree 실패 sigungu=%s: %s", sigungu, exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "카테고리 집계 중 오류가 발생했습니다"}},
        )

    return {
        "data": tree,
        "meta": {
            "sigungu": sigungu.strip(),
            "total_hospitals": total_hospitals,
            "total_categories": len(tree),
        },
    }
