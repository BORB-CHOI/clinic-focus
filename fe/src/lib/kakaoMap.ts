// 카카오맵 JavaScript SDK 동적 로더
//
// SDK는 <script> 태그를 한 번만 삽입. 같은 페이지에서 두 번 호출되더라도
// 캐시된 Promise를 그대로 반환해 중복 로드를 방지한다.
//
// `autoload=false` 옵션을 줘서 스크립트 onload 후 명시적으로
// `kakao.maps.load(cb)` 를 호출해야 maps 네임스페이스가 활성화됨.
// 이 패턴은 React StrictMode의 더블 렌더 때 race를 줄여준다.

import { KAKAO_MAP_KEY } from "@/lib/env";

// SDK가 노출하는 면 중에서 본 PoC가 실제로 쓰는 것만 좁게 선언
// (전체 d.ts를 받지 않는 대신 타입 안전성은 사용처 수준에서 확보)
export interface KakaoLatLng {
  getLat(): number;
  getLng(): number;
}

/** 지도 클릭 등 마우스 이벤트 — 클릭 좌표를 latLng 로 전달 */
export interface KakaoMouseEvent {
  latLng: KakaoLatLng;
}

export interface KakaoMap {
  setCenter(latlng: KakaoLatLng): void;
  setLevel(level: number): void;
  getLevel(): number;
  panTo(latlng: KakaoLatLng): void;
}

export interface KakaoMarker {
  setMap(map: KakaoMap | null): void;
  getPosition(): KakaoLatLng;
  setPosition(latlng: KakaoLatLng): void;
}

export interface KakaoCircle {
  setMap(map: KakaoMap | null): void;
  setRadius(radius: number): void;
  setPosition(latlng: KakaoLatLng): void;
}

export interface KakaoMarkerImage {
  // SDK 내부 객체. 본 코드에선 직접 호출하지 않음
  readonly __brand: "MarkerImage";
}

// 본 PoC가 의존하는 SDK 면을 모은 namespace 타입
export interface KakaoMapsApi {
  Map: new (
    container: HTMLElement,
    options: { center: KakaoLatLng; level: number },
  ) => KakaoMap;
  LatLng: new (lat: number, lng: number) => KakaoLatLng;
  Marker: new (options: {
    position: KakaoLatLng;
    map?: KakaoMap;
    image?: KakaoMarkerImage;
    title?: string;
  }) => KakaoMarker;
  MarkerImage: new (
    src: string,
    size: KakaoSize,
    options?: { offset?: KakaoPoint },
  ) => KakaoMarkerImage;
  Size: new (width: number, height: number) => KakaoSize;
  Point: new (x: number, y: number) => KakaoPoint;
  Circle: new (options: {
    center: KakaoLatLng;
    radius: number;
    strokeWeight?: number;
    strokeColor?: string;
    strokeOpacity?: number;
    strokeStyle?: string;
    fillColor?: string;
    fillOpacity?: number;
  }) => KakaoCircle;
  event: {
    addListener(
      target: KakaoMap | KakaoMarker,
      type: string,
      handler: (event?: KakaoMouseEvent) => void,
    ): void;
  };
  load(callback: () => void): void;
}

// SDK가 window 에 붙이는 네임스페이스. 가장 바깥의 `kakao.maps` 만 사용
export interface KakaoNamespace {
  maps: KakaoMapsApi;
}

interface KakaoWindow extends Window {
  kakao?: KakaoNamespace;
}

interface KakaoSize {
  readonly __brand: "Size";
}
interface KakaoPoint {
  readonly __brand: "Point";
}

const SCRIPT_ID = "kakao-map-sdk";
let loadPromise: Promise<KakaoMapsApi> | null = null;

/**
 * 카카오맵 SDK를 로드하고 `kakao.maps` 네임스페이스를 반환.
 * 키 미설정 시 reject.
 */
export function loadKakaoMaps(): Promise<KakaoMapsApi> {
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<KakaoMapsApi>((resolve, reject) => {
    if (!KAKAO_MAP_KEY) {
      reject(new Error("카카오맵 키가 설정되지 않았습니다"));
      return;
    }

    const win = window as KakaoWindow;

    // 이미 SDK가 로드돼 있고 maps 네임스페이스도 활성화된 경우
    if (win.kakao?.maps?.LatLng) {
      resolve(win.kakao.maps);
      return;
    }

    const onScriptReady = () => {
      const ns = (window as KakaoWindow).kakao;
      if (!ns) {
        reject(new Error("카카오맵 SDK 로드는 됐으나 네임스페이스가 비어있음"));
        return;
      }
      // autoload=false 라 명시적으로 활성화
      ns.maps.load(() => resolve(ns.maps));
    };

    const existing = document.getElementById(SCRIPT_ID);
    if (existing) {
      existing.addEventListener("load", onScriptReady, { once: true });
      existing.addEventListener(
        "error",
        () => reject(new Error("카카오맵 SDK 스크립트 로드 실패")),
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.async = true;
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(
      KAKAO_MAP_KEY,
    )}&autoload=false`;
    script.addEventListener("load", onScriptReady, { once: true });
    script.addEventListener(
      "error",
      () => {
        // 다음 호출에서 재시도 가능하도록 캐시 무효화
        loadPromise = null;
        reject(new Error("카카오맵 SDK 스크립트 로드 실패"));
      },
      { once: true },
    );
    document.head.appendChild(script);
  });

  return loadPromise;
}

// ── 신뢰도 색 마커 이미지 ────────────────────────────────────────────
// Tailwind 토큰 confidence.{high,medium,low}.500 와 동일한 hue 를 SVG 에
// 직접 박아 색상 정합성 유지 (모던 SaaS 톤: 에메랄드 + 앰버 + 슬레이트).
// 토큰 변경 시 tailwind.config.js 와 본 객체를 함께 갱신.
import type { ConfidenceLevel } from "@/types/domain";

const CONFIDENCE_HEX: Record<ConfidenceLevel, string> = {
  확실: "#10a667", //  hsl(151 81% 36%) ≈ 묵직한 그린
  추정: "#ea7c0c", //  hsl(28 92% 48%)  ≈ 따뜻한 오렌지
  "정보 부족": "#48536a", // hsl(215 19% 35%) ≈ 짙은 슬레이트
};

const MARKER_W = 28;
const MARKER_H = 36;

export function buildMarkerImage(
  maps: KakaoMapsApi,
  level: ConfidenceLevel,
): KakaoMarkerImage {
  const fill = CONFIDENCE_HEX[level];
  // 위는 둥글고 아래는 뾰족한 핀 모양 + 가운데 흰 점
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 36" width="28" height="36">
  <path d="M14 0 C6 0 0 6 0 14 C0 22 14 36 14 36 C14 36 28 22 28 14 C28 6 22 0 14 0 Z"
        fill="${fill}" stroke="white" stroke-width="2"/>
  <circle cx="14" cy="13" r="4.5" fill="white"/>
</svg>`.trim();

  const dataUri = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  const size = new maps.Size(MARKER_W, MARKER_H);
  const offset = new maps.Point(MARKER_W / 2, MARKER_H);
  return new maps.MarkerImage(dataUri, size, { offset });
}
