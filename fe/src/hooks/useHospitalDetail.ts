// 병원 상세 hook — /api/hospitals/{id} (TanStack Query)
//
// 상세 응답은 {data: HospitalDetail} 봉투(meta 없음). 9개 영역 데이터를 한 번에 받는다.
// 비-데모 병원은 ai_description·detailed_signals.vision·operating_hours 가 null 일 수 있어
// 호출부(페이지·섹션)에서 null-safe 렌더링 필요.

import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { HospitalDetail } from "@/types/domain";

export function useHospitalDetail(hospitalId: string | undefined) {
  return useQuery<HospitalDetail>({
    queryKey: ["hospital", hospitalId],
    queryFn: () =>
      apiGet<{ data: HospitalDetail }>(`/api/hospitals/${hospitalId}`).then(
        (r) => r.data,
      ),
    enabled: Boolean(hospitalId),
  });
}
