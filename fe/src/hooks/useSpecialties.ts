// 진료과목 목록 hook — GET /api/specialties?sigungu=강남구
//
// 진료과목 칩 줄에서 사용. 결과는 count 내림차순으로 BE 가 반환.
// staleTime 5분 — 진료과목 분포는 자주 바뀌지 않아 캐시 적극 활용.

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { SpecialtiesResponse } from "@/types/domain";

export function useSpecialties(sigungu: string) {
  return useQuery<SpecialtiesResponse>({
    queryKey: ["specialties", sigungu],
    queryFn: () =>
      apiGet<SpecialtiesResponse>("/api/specialties", { sigungu }),
    staleTime: 5 * 60_000, // 5분
    enabled: sigungu.length > 0,
  });
}
