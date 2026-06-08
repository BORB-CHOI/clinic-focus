// 검색 hook — /api/search (TanStack Query)
//
// - q 있으면 자연어 검색(KB Retrieve), 없으면 시군구 카테고리(DDB GSI). BE 가 경로 분기.
// - page 기반 페이지네이션: offset = (page-1) * PAGE_SIZE.
// - specialty, lat/lng/radius_km 인자 추가 — 진료과목 칩·지도 검색 재사용.
// - 검색·정렬·필터·페이지 모두 queryKey 에 묶여 변경 시 자동 refetch.

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { SearchResponse, SortOption } from "@/types/domain";

export const PAGE_SIZE = 20;
const POC_SIGUNGU = "강남구";

export interface SearchArgs {
  q: string;
  minConfidence: number;
  sort: SortOption;
  page?: number;        // 1-base, 기본 1
  specialty?: string;  // 진료과목 필터 (빈 문자열 = 전체) — 레거시, category 우선
  /** 계층형 카테고리 L1 key (specialty·etc 버킷 공용). specialty 대신 이걸 씀 */
  category?: string;
  /** L2 세부 시술·증상 태그. category 가 있을 때만 의미 있음 */
  focus?: string;
  /** 페이지 크기 오버라이드. 기본 PAGE_SIZE(20). 지도는 100으로 한 번에 마커 노출 */
  limit?: number;
  /** 지도 검색용. lat/lng/radius_km 모두 있어야 위치 검색으로 동작 */
  lat?: number;
  lng?: number;
  radius_km?: number;
  /** false 면 fetch 안 함(예: 진료과 둘러보기 랜딩에선 큰 목록을 굳이 안 받음). 기본 true */
  enabled?: boolean;
  // ── 심평원 필터 (카테고리/시군구 탐색 경로 전용) ──────────────────────
  /**
   * true 면 심평원 신고 기준 전문의 있는 병원만.
   * 자연어 q 가 있으면 BE 가 무시함 — UI 에서 q 없는 category 모드일 때만 활성화.
   */
  has_specialist?: boolean;
  /**
   * 특정 진료과 전문의 1명 이상 병원만.
   * has_specialist=true 와 병행 가능. 예: "피부과"
   */
  specialist_dept?: string;
}

export function useSearch({
  q,
  minConfidence,
  sort,
  page = 1,
  specialty,
  category,
  focus,
  limit = PAGE_SIZE,
  lat,
  lng,
  radius_km,
  enabled = true,
  has_specialist,
  specialist_dept,
}: SearchArgs) {
  const offset = (page - 1) * limit;

  // 심평원 필터는 카테고리 모드(q 없음)에서만 BE 에 전달.
  // q 있으면 BE 가 무시하지만, 불필요한 파라미터를 아예 보내지 않도록 프론트에서도 방어.
  const isNaturalSearch = Boolean(q);
  const hiraHasSpecialist = !isNaturalSearch ? has_specialist : undefined;
  const hiraSpecialistDept = !isNaturalSearch ? specialist_dept : undefined;

  return useQuery<SearchResponse>({
    enabled,
    queryKey: [
      "search", q, minConfidence, sort, page, specialty, category, focus,
      limit, lat, lng, radius_km,
      hiraHasSpecialist, hiraSpecialistDept,
    ],
    queryFn: ({ signal }) =>
      apiGet<SearchResponse>(
        "/api/search",
        {
          q: q || undefined,               // 비면 카테고리(시군구) 경로로
          sigungu: POC_SIGUNGU,
          min_confidence: minConfidence || undefined,
          sort,
          limit,
          offset,
          // category 가 있으면 category 우선; 없으면 레거시 specialty 사용
          category: category || undefined,
          focus: focus || undefined,       // L2 세부 시술·증상 필터
          specialty: (!category && specialty) ? specialty : undefined,
          lat,
          lng,
          radius_km,
          // 심평원 필터 — 카테고리 모드에서만 전달
          has_specialist: hiraHasSpecialist,
          specialist_dept: hiraSpecialistDept || undefined,
        },
        signal,
      ),
    // 필터/정렬/페이지 변경 시 이전 결과 유지해 깜빡임 방지
    placeholderData: (prev) => prev,
    // 전송 취소(AbortError)는 재시도하지 않음 — 정상 흐름
    retry: 1,
    staleTime: 60_000, // 1분 — 같은 쿼리는 1분간 캐시 재사용
  });
}
