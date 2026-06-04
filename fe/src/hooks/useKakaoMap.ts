import { useEffect, useRef, useState } from "react";

import {
  buildMarkerImage,
  loadKakaoMaps,
  type KakaoMap,
  type KakaoMapsApi,
  type KakaoMarker,
} from "@/lib/kakaoMap";
import type { SearchResultItem } from "@/types/domain";

interface UseKakaoMapOptions {
  /** 지도 초기 중심. 변경 시(예: GPS '내 위치') 지도를 그 좌표로 옮긴다 */
  center: { lat: number; lng: number };
  /** 지도 줌 레벨 (1=가까움 ~ 14=멈) */
  level?: number;
  /** 표시할 마커 데이터 */
  items: SearchResultItem[];
  /** 마커 클릭 시 해당 hospital_id 전달 */
  onMarkerClick?: (hospitalId: string) => void;
  /**
   * 지도 이동·줌이 멈췄을 때(idle) 현재 보이는 구역을 알린다.
   * center=현재 지도 중심, radiusKm=중심에서 화면 모서리까지(보이는 영역을 덮는 반경).
   * → 호출부가 이 좌표/반경으로 재검색하면 "보이는 구역의 병원"이 표시된다.
   * ※ 이 값을 다시 center prop 으로 되먹이면 idle 루프가 나므로, 호출부는 검색용
   *   별도 state 로만 쓰고 지도 center 로 피드백하지 말 것.
   */
  onIdle?: (center: { lat: number; lng: number }, radiusKm: number) => void;
  /** 선택된 병원 ID — 해당 마커를 크게/강조 표시 */
  selectedId?: string | null;
}

interface UseKakaoMapResult {
  mapRef: React.RefObject<HTMLDivElement>;
  status: "idle" | "loading" | "ready" | "error";
  error: string | null;
  /** 외부에서 지도 중심을 옮기고 싶을 때 */
  panTo: (lat: number, lng: number) => void;
}

function haversineKm(aLat: number, aLng: number, bLat: number, bLng: number): number {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat);
  const dLng = toRad(bLng - aLng);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// 카카오맵 인스턴스의 라이프사이클을 React 훅으로 감쌈.
// SDK 로드는 마운트 시 한 번. items/center 변동 시 마커·중심만 동기화(맵 재생성 X).
export function useKakaoMap({
  center,
  level = 4,
  items,
  onMarkerClick,
  onIdle,
  selectedId,
}: UseKakaoMapOptions): UseKakaoMapResult {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapsApiRef = useRef<KakaoMapsApi | null>(null);
  const mapInstanceRef = useRef<KakaoMap | null>(null);
  // hospital_id → { marker, item } — setImage 로 이미지만 교체하기 위해 item 보존
  const markersRef = useRef<Map<string, { marker: KakaoMarker; item: SearchResultItem }>>(new Map());

  const [status, setStatus] = useState<UseKakaoMapResult["status"]>("idle");
  const [error, setError] = useState<string | null>(null);

  // 콜백을 ref 에 담아 effect 의존성에서 분리
  const onMarkerClickRef = useRef(onMarkerClick);
  useEffect(() => { onMarkerClickRef.current = onMarkerClick; }, [onMarkerClick]);
  const onIdleRef = useRef(onIdle);
  useEffect(() => { onIdleRef.current = onIdle; }, [onIdle]);
  // selectedId 도 ref 로 — 마커 초기 생성 시 current value 참조용
  const selectedIdRef = useRef(selectedId);
  useEffect(() => { selectedIdRef.current = selectedId; }, [selectedId]);

  // ─ SDK 로드 + 맵 생성 (마운트 시 1회) ─────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setError(null);

    loadKakaoMaps()
      .then((maps) => {
        if (cancelled || !mapRef.current) return;
        mapsApiRef.current = maps;
        const map = new maps.Map(mapRef.current, {
          center: new maps.LatLng(center.lat, center.lng),
          level,
        });
        mapInstanceRef.current = map;

        // 이동·줌이 멈추면(idle) 현재 보이는 구역을 호출부에 알린다.
        // 보이는 영역을 덮도록 반경 = 중심 → 화면 모서리(NE) 거리.
        maps.event.addListener(map, "idle", () => {
          const c = map.getCenter();
          const b = map.getBounds();
          const ne = b.getNorthEast();
          const cl = c.getLat();
          const cn = c.getLng();
          const radiusKm = haversineKm(cl, cn, ne.getLat(), ne.getLng());
          onIdleRef.current?.({ lat: cl, lng: cn }, radiusKm);
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
      if (mapRef.current) mapRef.current.innerHTML = "";
      markersRef.current.clear();
      mapInstanceRef.current = null;
      mapsApiRef.current = null;
    };
    // 맵 재생성 방지: center/level 변동은 무시(아래 effect·panTo 에서 처리).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─ center 변동 시 이동 (외부 recenter, 예: GPS). idle 로부터 되먹이면 안 됨 ─
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

    markersRef.current.forEach(({ marker }) => marker.setMap(null));
    markersRef.current.clear();

    for (const item of items) {
      const position = new maps.LatLng(item.location.lat, item.location.lng);
      const isSelected = selectedIdRef.current === item.hospital_id;
      const image = buildMarkerImage(maps, item.confidence?.level, isSelected);
      const marker = new maps.Marker({ position, map, image, title: item.name });
      maps.event.addListener(marker, "click", () => {
        onMarkerClickRef.current?.(item.hospital_id);
      });
      markersRef.current.set(item.hospital_id, { marker, item });
    }

    return () => {
      markersRef.current.forEach(({ marker }) => marker.setMap(null));
      markersRef.current.clear();
    };
  }, [items, status]);

  // ─ 선택 마커 강조 (items 재생성 없이 이미지만 교체) ───────────────
  useEffect(() => {
    const maps = mapsApiRef.current;
    if (!maps || status !== "ready") return;
    markersRef.current.forEach(({ marker, item }) => {
      const isSelected = item.hospital_id === selectedId;
      marker.setImage(buildMarkerImage(maps, item.confidence?.level, isSelected));
    });
  }, [selectedId, status]);

  const panTo = (lat: number, lng: number) => {
    const map = mapInstanceRef.current;
    const maps = mapsApiRef.current;
    if (!map || !maps) return;
    map.panTo(new maps.LatLng(lat, lng));
  };

  return { mapRef, status, error, panTo };
}
