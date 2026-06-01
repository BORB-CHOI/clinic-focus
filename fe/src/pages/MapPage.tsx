import { useEffect, useMemo, useRef, useState } from "react";
import { Locate } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfidenceLegend } from "@/components/map/ConfidenceLegend";
import {
  RadiusSelector,
  type RadiusKm,
} from "@/components/map/RadiusSelector";
import { HospitalCard } from "@/components/search/HospitalCard";
import { EmptyState } from "@/components/common/EmptyState";
import { WarningBanner } from "@/components/common/WarningBanner";
import { useKakaoMap } from "@/hooks/useKakaoMap";
import { useSearch } from "@/hooks/useSearch";
import { HAS_KAKAO_MAP_KEY } from "@/lib/env";
import { cn } from "@/lib/utils";

// 지도 검색 페이지 — 실 /api/search 위치 검색 연동 (목업 제거)
//
// 좌측 풀 높이 지도 + 우측 사이드(컨트롤·선택 카드·반경 내 리스트) 2단 구성.
// 기본 중심 = 강남역 (데이터가 강남구 기준). GPS 거부 시 강남 유지.
// center/radiusKm 변경 시 /api/search?lat&lng&radius_km&sigungu=강남구&limit=100 refetch.

// 강남역 좌표 (데이터 = 강남구)
const FALLBACK_CENTER = { lat: 37.4979, lng: 127.0276 };
const DEFAULT_RADIUS: RadiusKm = 3;

export default function MapPage() {
  const [center, setCenter] = useState(FALLBACK_CENTER);
  const [radiusKm, setRadiusKm] = useState<RadiusKm>(DEFAULT_RADIUS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [geoMessage, setGeoMessage] = useState<string | null>(null);
  const selectedCardRef = useRef<HTMLDivElement>(null);

  // 마운트 시 GPS 시도하지 않음 — 강남 데이터 기준 PoC라 강남 밖이면 결과 없음이 정상.
  // "내 위치" 버튼으로 수동 GPS 점프는 유지.

  // 실 API — center/radiusKm 변경 시 자동 refetch. 지도는 페이지네이션 없이
  // 반경 내 병원을 한 번에 마커로 깔아야 하므로 limit=100 (BE 상한 le=100).
  const { data, isLoading } = useSearch({
    q: "",           // 카테고리(위치) 경로
    minConfidence: 0,
    sort: "distance",
    lat: center.lat,
    lng: center.lng,
    radius_km: radiusKm,
    limit: 100,
  });

  const items = useMemo(() => data?.data ?? [], [data]);

  // 마커 데이터: BE 응답의 distance_km 사용 (프론트 haversine 재계산 불필요)
  const visibleItems = useMemo(
    () => [...items].sort((a, b) => (a.distance_km ?? 0) - (b.distance_km ?? 0)),
    [items],
  );

  const selectedItem = useMemo(
    () => visibleItems.find((item) => item.hospital_id === selectedId) ?? null,
    [selectedId, visibleItems],
  );

  // 마커 클릭 시 사이드 카드로 스크롤
  useEffect(() => {
    if (selectedItem) {
      selectedCardRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [selectedItem]);

  const { mapRef, status, error } = useKakaoMap({
    center,
    items: visibleItems,
    radiusKm,
    onMarkerClick: setSelectedId,
  });

  function handleRecenter() {
    if (!("geolocation" in navigator)) {
      setGeoMessage("이 브라우저는 위치 정보를 지원하지 않습니다");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCenter({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setGeoMessage(null);
      },
      () =>
        setGeoMessage(
          "위치 권한이 없어 현재 위치를 가져오지 못했습니다 — 강남 중심으로 표시합니다",
        ),
    );
  }

  return (
    <section className="space-y-3">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">지도 검색</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          강남 중심으로 반경 내 병원을 근거 등급 색 마커로 표시합니다.
        </p>
      </header>

      {geoMessage ? <WarningBanner message={geoMessage} /> : null}

      {/* 컨트롤 바 — 반경·범례·내위치·결과 카운트 */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-card p-3">
        <RadiusSelector value={radiusKm} onChange={setRadiusKm} />

        <div className="hidden h-5 w-px bg-border sm:block" aria-hidden />

        <ConfidenceLegend />

        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {isLoading ? (
              <span className="animate-pulse">불러오는 중…</span>
            ) : (
              <>
                <span className="text-base font-semibold text-foreground">
                  {visibleItems.length}
                </span>
                <span className="ml-1">건</span>
              </>
            )}
          </span>
          <Button variant="outline" size="sm" onClick={handleRecenter}>
            <Locate className="h-4 w-4" aria-hidden />
            내 위치
          </Button>
        </div>
      </div>

      {/* 메인: 지도 + 사이드 */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_420px]">
        {/* 지도 */}
        <div className="space-y-2">
          {HAS_KAKAO_MAP_KEY ? (
            <>
              <div
                ref={mapRef}
                role="region"
                aria-label="병원 지도"
                className="h-[560px] w-full overflow-hidden rounded-lg border bg-muted shadow-sm"
              />
              {status === "loading" ? (
                <p className="text-xs text-muted-foreground">
                  카카오맵 SDK를 불러오는 중…
                </p>
              ) : null}
              {status === "error" ? (
                <WarningBanner
                  message={`지도 로드 실패: ${error ?? "알 수 없는 오류"}`}
                />
              ) : null}
            </>
          ) : (
            <KeyMissingFallback />
          )}
        </div>

        {/* 사이드 */}
        <aside className="space-y-4">
          {/* 선택한 병원 */}
          <div ref={selectedCardRef} className="space-y-2 scroll-mt-20">
            <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              선택한 병원
              {selectedItem ? (
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium normal-case tracking-normal text-primary">
                  마커 클릭됨
                </span>
              ) : null}
            </h2>
            {selectedItem ? (
              <HospitalCard item={selectedItem} compact />
            ) : visibleItems.length === 0 && !isLoading ? (
              <EmptyState message="반경 내 병원이 없습니다 — 반경을 넓혀보세요" />
            ) : (
              <EmptyState message="지도에서 마커를 클릭하면 카드가 여기에 표시됩니다" />
            )}
          </div>

          {/* 반경 내 리스트 — 항상 노출. 키 유무와 무관하게 시연 가능하도록 */}
          {visibleItems.length > 0 ? (
            <div className="space-y-2">
              <h3 className="flex items-baseline justify-between gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <span>
                  반경 내 (거리순)
                  <span className="ml-1 normal-case tracking-normal text-muted-foreground/70">
                    {radiusKm < 1 ? `${radiusKm * 1000}m` : `${radiusKm}km`} ·{" "}
                    {visibleItems.length}건
                  </span>
                </span>
              </h3>
              <ul className="grid max-h-[480px] gap-2 overflow-y-auto pr-1">
                {visibleItems.map((item, i) => (
                  <li
                    key={item.hospital_id}
                    className="animate-in fade-in slide-in-from-bottom-1 fill-mode-both duration-300"
                    style={{ animationDelay: `${Math.min(i, 10) * 30}ms` }}
                  >
                    <HospitalCard
                      item={item}
                      compact
                      className={cn(
                        "transition-shadow",
                        selectedId === item.hospital_id &&
                          "ring-2 ring-primary ring-offset-1",
                      )}
                    />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </aside>
      </div>
    </section>
  );
}

function KeyMissingFallback() {
  return (
    <div className="flex h-[560px] flex-col items-center justify-center rounded-lg border border-dashed bg-muted/40 p-6 text-center">
      <p className="text-sm font-semibold">카카오맵 키가 설정되지 않았습니다</p>
      <p className="mt-2 max-w-md text-xs text-muted-foreground">
        <code>fe/.env.local</code> 에{" "}
        <code>VITE_KAKAO_MAP_KEY=&lt;발급받은_JS_키&gt;</code> 를 넣은 뒤 dev
        서버를 재시작하면 지도가 표시됩니다.
        <br />
        지금은 우측 리스트에서 반경 내 병원을 거리순으로 확인할 수 있습니다.
      </p>
    </div>
  );
}
