import type { AdItem } from "@/types/ads";

// PoC 광고 mock — BE 광고 엔드포인트 부재 단계의 시연용 데이터.
//
// 실제 연동 시 GET /api/ads?specialty=&sigungu= 로 교체하고 이 모듈만 갈아끼운다.
// 카피는 전부 "병원이 자기 사이트에서 ~로 표시" 주체 명시 원칙 준수
// (평가형 표현 금지 — '잘한다/최고' X).
const ADS: AdItem[] = [
  {
    ad_id: "ad_derma_01",
    hospital_id: null,
    name: "강남스마트피부과의원",
    standard_specialty: "피부과",
    primary_focus: ["여드름·아토피"],
    tagline: "자기 사이트에서 여드름·아토피 일반 진료를 메인으로 표시한 의원",
    location_label: "강남구 역삼동",
    thumbnail_url: null,
    landing_url: null,
  },
  {
    ad_id: "ad_ortho_01",
    hospital_id: null,
    name: "바른어깨정형외과",
    standard_specialty: "정형외과",
    primary_focus: ["어깨·견관절"],
    tagline: "자기 사이트에서 어깨·회전근개를 주력으로 소개한 정형외과",
    location_label: "강남구 논현동",
    thumbnail_url: null,
    landing_url: null,
  },
];

// 진료과 컨텍스트에 맞는 광고를 우선 노출. 매칭 없으면 일반 광고 fallback.
// limit 으로 슬롯 수 제한 (검색 결과 상단 1개가 기본).
export function getAds(opts?: { specialty?: string; limit?: number }): AdItem[] {
  const { specialty, limit = 1 } = opts ?? {};
  const matched = specialty
    ? ADS.filter((ad) => ad.standard_specialty === specialty)
    : [];
  const pool = matched.length > 0 ? matched : ADS;
  return pool.slice(0, limit);
}
