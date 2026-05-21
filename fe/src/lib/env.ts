// Vite의 import.meta.env 접근을 한 곳으로 모은다
//
// - 컴포넌트에서 직접 `import.meta.env.VITE_*` 를 흩뿌리지 않음
// - 미설정/빈 문자열을 빈 값으로 정규화 (vite-env.d.ts는 string으로 선언돼 있지만
//   실제로는 .env 누락 시 undefined가 들어와 런타임 분기가 갈라짐)
// - 4단계: 카카오맵 키 폴백 (키 없으면 안내 카드)
// - 5단계: BE base URL을 fetch wrapper에서 단일 참조

function readString(value: string | undefined): string {
  return (value ?? "").trim();
}

/** API base URL — 끝의 `/`는 제거해 fetch 시 `//` 발생 방지 */
export const API_BASE_URL: string = readString(
  import.meta.env.VITE_API_BASE_URL,
).replace(/\/+$/, "");

/** 카카오맵 JavaScript 키. 미설정이면 빈 문자열 */
export const KAKAO_MAP_KEY: string = readString(
  import.meta.env.VITE_KAKAO_MAP_KEY,
);

/** 키 존재 여부. 4단계 지도 폴백 분기용 */
export const HAS_KAKAO_MAP_KEY: boolean = KAKAO_MAP_KEY.length > 0;
