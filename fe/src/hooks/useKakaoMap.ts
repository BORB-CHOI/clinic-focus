import { useEffect, useRef, useState } from "react";

import {
  buildMarkerImage,
  loadKakaoMaps,
  type KakaoCircle,
  type KakaoMap,
  type KakaoMapsApi,
  type KakaoMarker,
} from "@/lib/kakaoMap";
import type { SearchResultItem } from "@/types/domain";

interface UseKakaoMapOptions {
  /** 지도 초기 중심 (사용자 위치 또는 기본값) */
  center: { lat: number; lng: number };
  /** 지도 줌 레벨 (1=가까움 ~ 14=멈) */
  level?: number;
  /** 표시할 마커 데이터 */
  items: SearchResultItem[];
  /** 반경 원 (km). undefined면 원 미표시 */
  radiusKm?: number;
  /** 마커 클릭 시 해당 hospital_id 전달 */
  onMarkerClick?: (hospitalId: string) => void;
}

interface UseKakaoMapResult {
  /** 지도 컨테이너 div 에 붙일 ref */
  mapRef: React.RefObject<HTMLDivElement>;
  /** SDK 로드·맵 생성 단계 */
  status: "idle" | "loading" | "ready" | "error";
  /** error 상태일 때의 에러 메시지 */
  error: string | null;
  /** 외부에서 지도 중심을 옮기고 싶을 때 사용 */
  panTo: (lat: number, lng: number) => void;
}

// 카카오맵 인스턴스의 라이프사이클을 React 훅으로 감쌈.
//
// SDK 로드는 마운트 시 한 번. items/center/radius 변동 시에는
// 마커·원만 동기화하고 맵 자체는 재생성하지 않는다.
export function useKakaoMap({
  center,
  level = 4,
  items,
  radiusKm,
  onMarkerClick,
}: UseKakaoMapOptions): UseKakaoMapResult {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapsApiRef = useRef<KakaoMapsApi | null>(null);
  const mapInstanceRef = useRef<KakaoMap | null>(null);
  const markersRef = useRef<KakaoMarker[]>([]);
  const circleRef = useRef<KakaoCircle | null>(null);

  const [status, setStatus] = useState<UseKakaoMapResult["status"]>("idle");
  const [error, setError] = useState<string | null>(null);

  // 콜백을 ref 에 담아 effect 의존성에서 분리
  const onMarkerClickRef = useRef(onMarkerClick);
  useEffect(() => {
    onMarkerClickRef.current = onMarkerClick;
  }, [onMarkerClick]);

  // ─ SDK 로드 + 맵 생성 (마운트 시 1회) ─────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setError(null);

    loadKakaoMaps()
      .then((maps) => {
        if (cancelled || !mapRef.current) return;
        mapsApiRef.current = maps;
        mapInstanceRef.current = new maps.Map(mapRef.current, {
          center: new maps.LatLng(center.lat, center.lng),
          level,
        });
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setStatus("error");
        setError(err instanceof Error ? err.message : String(err));
      });

    return () => {
      cancelled = true;
    };
    // 맵 재생성을 막기 위해 center/level 변동은 무시. 변경은 panTo 또는
    // 별도 effect 에서 setCenter 로 처리.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─ center 변동 시 부드럽게 이동 (재생성 X) ────────────────────────
  useEffect(() => {
    const map = mapInstanceRef.current;
    const maps = mapsApiRef.current;
    if (!map || !maps || status !== "ready") return;
    map.setCenter(new maps.LatLng(center.lat, center.lng));
  }, [center.lat, center.lng, status]);

  // ─ 마커 동기화 ───────────────────────────────────────────────────
  useEffect(() => {
    const map = mapInstanceRef.current;
    const maps = mapsApiRef.current;
    if (!map || !maps || status !== "ready") return;

    // 기존 마커 정리
    for (const m of markersRef.current) m.setMap(null);
    markersRef.current = [];

    // 새 마커 부착
    for (const item of items) {
      const position = new maps.LatLng(item.location.lat, item.location.lng);
      const image = buildMarkerImage(maps, item.confidence.level);
      const marker = new maps.Marker({ position, map, image, title: item.name });
      maps.event.addListener(marker, "click", () => {
        onMarkerClickRef.current?.(item.hospital_id);
      });
      markersRef.current.push(marker);
    }

    return () => {
      for (const m of markersRef.current) m.setMap(null);
      markersRef.current = [];
    };
  }, [items, status]);

  // ─ 반경 원 동기화 ────────────────────────────────────────────────
  useEffect(() => {
    const map = mapInstanceRef.current;
    const maps = mapsApiRef.current;
    if (!map || !maps || status !== "ready") return;

    // 기존 원 제거
    if (circleRef.current) {
      circleRef.current.setMap(null);
      circleRef.current = null;
    }

    if (radiusKm && radiusKm > 0) {
      const circle = new maps.Circle({
        center: new maps.LatLng(center.lat, center.lng),
        radius: radiusKm * 1000, // m
        strokeWeight: 1,
        strokeColor: "#2563eb",
        strokeOpacity: 0.5,
        strokeStyle: "dashed",
        fillColor: "#2563eb",
        fillOpacity: 0.06,
      });
      circle.setMap(map);
      circleRef.current = circle;
    }

    return () => {
      if (circleRef.current) {
        circleRef.current.setMap(null);
        circleRef.current = null;
      }
    };
  }, [radiusKm, center.lat, center.lng, status]);

  const panTo = (lat: number, lng: number) => {
    const map = mapInstanceRef.current;
    const maps = mapsApiRef.current;
    if (!map || !maps) return;
    map.panTo(new maps.LatLng(lat, lng));
  };

  return { mapRef, status, error, panTo };
}
