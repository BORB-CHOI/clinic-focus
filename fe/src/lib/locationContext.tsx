import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { searchPlace } from "@/lib/kakaoMap";

// 전역 위치 상태 — 헤더의 위치 검색 툴바와 지도(MapPage)가 공유한다.
//
// 헤더에서 장소를 검색하거나 "내 위치"를 누르면 center 가 갱신되고,
// MapPage 는 이 center 를 지도 중심으로 사용한다. 지도를 드래그·줌 하는
// 뷰포트(searchArea) 갱신은 MapPage 로컬 책임이라 여기엔 두지 않는다
// (idle 값을 center 로 되먹이면 무한 루프).

export interface LatLng {
  lat: number;
  lng: number;
}

// 강남역 — 데이터(강남구) 기준 기본 중심
const FALLBACK_CENTER: LatLng = { lat: 37.4979, lng: 127.0276 };

interface LocationContextValue {
  /** 지도 중심으로 쓸 좌표 (검색·GPS 로만 갱신). 기본 강남역 */
  center: LatLng;
  /** 표시용 위치 라벨. 미설정이면 null */
  label: string | null;
  /** 위치가 사용자에 의해 설정됐는지 (기본값 사용 중이면 false) */
  hasLocation: boolean;
  /** 검색 중 여부 */
  searching: boolean;
  /** 장소 검색 실패 메시지 */
  error: string | null;
  /** GPS 등 안내 메시지 */
  message: string | null;
  /** 장소명으로 검색 → center·label 갱신 */
  searchByName: (query: string) => void;
  /** 브라우저 GPS 로 현재 위치 */
  useMyLocation: () => void;
  /** 에러·메시지 클리어 */
  clearFeedback: () => void;
}

const LocationContext = createContext<LocationContextValue | null>(null);

export function LocationProvider({ children }: { children: ReactNode }) {
  const [center, setCenter] = useState<LatLng>(FALLBACK_CENTER);
  const [label, setLabel] = useState<string | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const searchByName = useCallback((query: string) => {
    const q = query.trim();
    if (!q) return;
    setError(null);
    setMessage(null);
    setSearching(true);
    searchPlace(q)
      .then(({ lat, lng, name }) => {
        setCenter({ lat, lng });
        setLabel(name);
      })
      .catch(() =>
        setError("장소를 찾을 수 없습니다 — 다른 이름으로 시도해보세요"),
      )
      .finally(() => setSearching(false));
  }, []);

  const useMyLocation = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setMessage("이 브라우저는 위치 정보를 지원하지 않습니다");
      return;
    }
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCenter({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLabel("내 위치");
        setMessage(null);
      },
      () =>
        setMessage(
          "위치 권한이 없어 현재 위치를 가져오지 못했습니다 — 강남 중심으로 표시합니다",
        ),
    );
  }, []);

  const clearFeedback = useCallback(() => {
    setError(null);
    setMessage(null);
  }, []);

  const value = useMemo<LocationContextValue>(
    () => ({
      center,
      label,
      hasLocation: label !== null,
      searching,
      error,
      message,
      searchByName,
      useMyLocation,
      clearFeedback,
    }),
    [center, label, searching, error, message, searchByName, useMyLocation, clearFeedback],
  );

  return (
    <LocationContext.Provider value={value}>
      {children}
    </LocationContext.Provider>
  );
}

export function useLocationStore(): LocationContextValue {
  const ctx = useContext(LocationContext);
  if (!ctx) {
    throw new Error("useLocationStore must be used within LocationProvider");
  }
  return ctx;
}
