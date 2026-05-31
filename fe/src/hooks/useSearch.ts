// 검색 hook — /api/search (TanStack Query)
//
// - q 있으면 자연어 검색(KB Retrieve), 없으면 시군구 카테고리(DDB GSI). BE 가 경로 분기.
// - PoC 스코프라 sigungu="강남구" 고정. min_confidence·sort 는 BE 가 서버사이드 처리.
// - 검색·정렬·필터 모두 queryKey 에 묶여 URL 파라미터 변경 시 자동 refetch.

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { SearchResponse, SortOption } from "@/types/domain";

const POC_SIGUNGU = "강남구";

export interface SearchArgs {
  q: string;
  minConfidence: number;
  sort: SortOption;
}

export function useSearch({ q, minConfidence, sort }: SearchArgs) {
  return useQuery<SearchResponse>({
    queryKey: ["search", q, minConfidence, sort],
    queryFn: () =>
      apiGet<SearchResponse>("/api/search", {
        q: q || undefined, // 비면 카테고리(시군구) 경로로
        sigungu: POC_SIGUNGU,
        min_confidence: minConfidence,
        sort,
        limit: 30,
      }),
    // 필터/정렬 토글 시 이전 결과 유지해 깜빡임 방지
    placeholderData: (prev) => prev,
  });
}
