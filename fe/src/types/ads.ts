// 광고(협찬) 슬롯 타입 — 유기적 검색 결과(SearchResultItem)와 구분.
//
// 의료법 §56 / 광고 투명성: 협찬 콘텐츠는 반드시 "광고" 라벨로 명시하고
// 자연 검색 결과와 시각적으로 분리한다. 본 서비스는 평가하지 않으며,
// 광고 카피도 "병원이 자기 사이트에서 ~로 표시" 형태의 주체 명시를 따른다.
//
// PoC 단계라 BE 광고 엔드포인트는 없다. FE 는 정적 mock(ADS) 로 슬롯 UI 만 시연.

export interface AdItem {
  /** 광고 식별자 */
  ad_id: string;
  /** 연결되는 병원 상세 (있으면 카드 클릭 시 상세로 이동) */
  hospital_id: string | null;
  /** 광고주 표기명 (병원명) */
  name: string;
  /** 표준 진료과목 */
  standard_specialty: string;
  /** 병원이 자기 사이트에서 내세운 주력 — 주체 명시 카피 */
  primary_focus: string[];
  /** 한 줄 카피 (광고주 제공) */
  tagline: string;
  /** 위치 표기 (시군구 등) */
  location_label: string;
  /** 대표 이미지 URL. null 이면 플레이스홀더 */
  thumbnail_url: string | null;
  /** 외부 랜딩 URL (hospital_id 가 null 일 때 사용) */
  landing_url: string | null;
}
