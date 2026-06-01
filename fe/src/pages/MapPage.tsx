import { useEffect, useMemo, useRef, useState } from "react";
import { Locate } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfidenceLegend } from "@/components/map/ConfidenceLegend";
import { HospitalCard } from "@/components/search/HospitalCard";
import { EmptyState } from "@/components/common/EmptyState";
import { WarningBanner } from "@/components/common/WarningBanner";
import { useKakaoMap } from "@/hooks/useKakaoMap";
import { useSearch } from "@/hooks/useSearch";
import { HAS_KAKAO_MAP_KEY } from "@/lib/env";
import { cn } from "@/lib/utils";

// 지도 검색 페이지 — 뷰포트(보이는 구역) 기반 검색.
//
// 지도를 드래그·줌하면(idle) 그때 보이는 영역을 덮는 중심·반경으로 /api/search 위치검색을
// 다시 호출해, "지금 화면에 보이는 구역의 병원"을 마커로 깐다. 반경 선택·핀 찍기는 없다.
// ★검색영역(searchArea)은 지도 center prop 과 분리한다 — idle 값을 center 로 되먹이면
//   map.setCenter ↔ idle 무한 루프(흰 화면)가 난다.

// 강남역 좌표 (데이터 = 강남구). GPS '내 위치' 또는 초기 중심.
const FALLBACK_CENTER = { lat: 37.4979, lng: 127.0276 };
const MAX_RADIUS_KM = 30; // BE /api/search radius_km le=30 — 너무 줌아웃해도 캡

export default function MapPage() {
  // 지도 중심(초기·GPS recenter 전용). idle 로부터 되먹이지 않는다.
  const [center, setCenter] = useState(FALLBACK_CENTER);
  // 실제 검색에 쓰는 영역 — 지도 idle 이 채운다. 초기값은 강남역 3km.
  const [searchArea, setSearchArea] = useState({
    lat: FALLBACK_CENTER.lat,
    lng: FALLBACK_CENTER.lng,
    radiusKm: 3,
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [geoMessage, setGeoMessage] = useState<string | null>(null);
  const selectedCardRef = useRef<HTMLDivElement>(null);

  // 보이는 구역 위치검색. 한 화면에 마커를 한 번에 깔아야 하므로 limit=100(BE 상한).
  const { data, isLoading } = useSearch({
    q: "",
    minConfidence: 0,
    sort: "distance",
    lat: searchArea.lat,
    lng: searchArea.lng,
    radius_km: searchArea.radiusKm,
    limit: 100,
  });

  const items = useMemo(() => data?.data ?? [], [data]);
  const visibleItems = useMemo(
    () => [...items].sort((a, b) => (a.distance_km ?? 0) - (b.distance_km ?? 0)),
    [items],
  );

  const selectedItem = useMemo(
    () => visibleItems.find((item) => item.hospital_id === selectedId) ?? null,
    [selectedId, visibleItems],
  );

  useEffect(() => {
    if (selectedItem) {
      selectedCardRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [selectedItem]);

  const { mapRef, status, error } = useKakaoMap({
    center,
    items: visibleItems,
    onMarkerClick: setSelectedId,
    // 지도 이동·줌 멈추면 보이는 구역으로 재검색 (center prop 에는 되먹이지 않음 = 루프 차단)
    onIdle: (c, radiusKm) =>
      setSearchArea({
        lat: c.lat,
        lng: c.lng,
        radiusKm: Math.min(Math.max(radiusKm, 0.3), MAX_RADIUS_KM),
      }),
  });

  function handleRecenter() {
    if (!("geolocation" in navigator)) {
      setGeoMessage("이 브라우저는 위치 정보를 지원하지 않습니다");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        // center 만 바꾼다 → 지도가 그 위치로 이동 → idle → searchArea 자동 갱신
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
          <strong>지도를 움직이거나 확대</strong>하면 그때 보이는 구역의 병원을 근거 등급 색
          마커로 다시 표시합니다.
        </p>
      </header>

      {geoMessage ? <WarningBanner message={geoMessage} /> : null}

      {/* 컨트롤 바 — 범례·결과 카운트·내위치 */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-card p-3">
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
              <EmptyState message="이 구역에 병원이 없습니다 — 지도를 옮기거나 확대해보세요" />
            ) : (
              <EmptyState message="지도에서 마커를 클릭하면 카드가 여기에 표시됩니다" />
            )}
          </div>

          {/* 보이는 구역 리스트 — 거리순. 키 유무와 무관하게 시연 가능하도록 항상 노출 */}
          {visibleItems.length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                보이는 구역 (거리순)
                <span className="ml-1 normal-case tracking-normal text-muted-foreground/70">
                  {visibleItems.length}건
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
        지금은 우측 리스트에서 강남 중심 병원을 거리순으로 확인할 수 있습니다.
      </p>
    </div>
  );
}
