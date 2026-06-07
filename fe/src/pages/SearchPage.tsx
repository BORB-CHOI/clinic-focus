import { useSearchParams } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

import { CategoryGrid } from "@/components/search/CategoryGrid";
import { EmptyState } from "@/components/common/EmptyState";
import { RecommendSection } from "@/components/analytics/RecommendSection";
import { WeatherBadge } from "@/components/analytics/WeatherBadge";
import { AdCard } from "@/components/search/AdCard";
import { HospitalCard } from "@/components/search/HospitalCard";
import { HospitalCardSkeleton } from "@/components/search/HospitalCardSkeleton";
import { Pagination } from "@/components/search/Pagination";
import { SearchFilters } from "@/components/search/SearchFilters";
import { useSearch, PAGE_SIZE } from "@/hooks/useSearch";
import { useSpecialties } from "@/hooks/useSpecialties";
import { isEmergencyQuery } from "@/lib/emergency";
import { getAds } from "@/lib/ads";
import type { SortOption } from "@/types/domain";

// 검색 결과 페이지 — BE /api/search 연동 (useSearch hook)
//
// 3가지 모드(URL 파라미터로 결정):
//   - 둘러보기(browse): q·specialty·all 없음 → 진료과목 그리드 랜딩(닥터나우/모두닥/굿닥식)
//   - 카테고리(category): specialty 또는 all=1 → 해당 진료과(또는 전체) 목록 + 필터·정렬·페이지
//   - 자연어(search): q 있음 → KB 검색 결과 목록
// 상태는 전부 URL 쿼리스트링에 묶어 새로고침·뒤로가기·공유에서 보존.

const POC_SIGUNGU = "강남구";

const SEARCH_MODE_LABEL: Record<string, string> = {
  natural: "자연어",
  nearby: "근처",
  "natural+nearby": "자연어+근처",
  category: "카테고리",
};

const VALID_SORTS: SortOption[] = ["distance", "confidence", "relevance", "popular"];

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const query = searchParams.get("q") ?? "";
  const specialty = searchParams.get("specialty") ?? "";
  const showAll = searchParams.get("all") === "1";

  // 모드: 질의·진료과·전체 다 없으면 둘러보기(그리드 랜딩)
  const isBrowse = !query && !specialty && !showAll;

  const minConfidenceParam = Number.parseInt(
    searchParams.get("min_confidence") ?? "0",
    10,
  );
  const minConfidence = Number.isFinite(minConfidenceParam)
    ? minConfidenceParam
    : 0;

  const sortParam = searchParams.get("sort") as SortOption | null;
  const sort: SortOption = VALID_SORTS.includes(sortParam ?? ("" as SortOption))
    ? (sortParam as SortOption)
    : "relevance";

  const pageParam = Number.parseInt(searchParams.get("page") ?? "1", 10);
  const page = Number.isFinite(pageParam) && pageParam >= 1 ? pageParam : 1;

  // ── 파라미터 변경 핸들러 ──────────────────────────────────────────────

  const setMinConfidence = (value: number) => {
    const next = new URLSearchParams(searchParams);
    if (value === 0) next.delete("min_confidence");
    else next.set("min_confidence", String(value));
    next.delete("page");
    setSearchParams(next, { replace: true });
  };

  const setSort = (value: SortOption) => {
    const next = new URLSearchParams(searchParams);
    if (value === "relevance") next.delete("sort");
    else next.set("sort", value);
    next.delete("page");
    setSearchParams(next, { replace: true });
  };

  // 그리드 타일 선택 → 그 진료과로 드릴인 (""=전체 병원 보기)
  const selectCategory = (value: string) => {
    const next = new URLSearchParams(searchParams);
    next.delete("q");
    next.delete("page");
    if (value === "") {
      next.delete("specialty");
      next.set("all", "1");
    } else {
      next.set("specialty", value);
      next.delete("all");
    }
    setSearchParams(next, { replace: false });
  };

  // 목록 → 그리드 랜딩으로 복귀 (질의·진료과·전체·페이지 해제)
  const backToBrowse = () => {
    const next = new URLSearchParams(searchParams);
    ["q", "specialty", "all", "page"].forEach((k) => next.delete(k));
    setSearchParams(next, { replace: false });
  };

  const setPage = (value: number) => {
    const next = new URLSearchParams(searchParams);
    if (value <= 1) next.delete("page");
    else next.set("page", String(value));
    setSearchParams(next, { replace: true });
  };

  // ── 데이터 fetch ──────────────────────────────────────────────────────
  // 둘러보기 모드에선 큰 카테고리 목록을 굳이 받지 않는다(enabled=false).

  const { data, isLoading, isError, error } = useSearch({
    q: query,
    minConfidence,
    sort,
    page,
    specialty,
    enabled: !isBrowse,
  });

  const { data: specialtiesData, isLoading: specialtiesLoading } =
    useSpecialties(POC_SIGUNGU);

  const items = data?.data ?? [];
  const meta = data?.meta;
  const total = meta?.total ?? 0;

  // 광고 슬롯 — 결과 목록 첫 페이지 상단에만 노출. 진료과 컨텍스트로 매칭.
  // 응급 쿼리에선 광고를 숨긴다 (응급 상황에 협찬 노출은 부적절).
  const ads =
    page === 1 && !isEmergencyQuery(query)
      ? getAds({ specialty, limit: 1 })
      : [];

  // 목록 제목
  const listTitle = query
    ? `“${query}” 검색 결과`
    : specialty
      ? specialty
      : "강남구 전체 병원";

  return (
    <section className="space-y-5">
      <div className="animate-in fade-in slide-in-from-top-1 duration-300">
        <h1 className="text-2xl font-bold tracking-tight">병원 검색</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          표준 진료과목 너머, 이 병원이 자기 사이트에서 무엇을 메인으로
          표시하는지를 보여줍니다.
        </p>
      </div>

      <div className="animate-in fade-in slide-in-from-top-1 duration-300 rounded-md border bg-muted/25 px-3 py-2">
        <WeatherBadge />
      </div>

      {isEmergencyQuery(query) ? (
        <div
          role="alert"
          className="animate-in fade-in slide-in-from-top-2 duration-300 rounded-lg border-2 border-red-300 bg-red-50 p-4 text-sm leading-relaxed text-red-800"
        >
          <p className="text-base font-bold">응급 상황으로 보입니다</p>
          <p className="mt-1">
            지금 <strong>119에 전화</strong>하거나 가까운 <strong>응급실</strong>로 바로 가세요.
            이 서비스는 병원이 무엇에 주력하는지 보여줄 뿐, <strong>응급 진료기관을 추천하지
            않습니다</strong>. 아래 검색 결과를 응급 판단에 사용하지 마세요.
          </p>
        </div>
      ) : null}

      {isBrowse ? (
        /* ── 둘러보기: 트렌딩 + 진료과목 그리드 랜딩 ── */
        <div className="space-y-5">
          <RecommendSection />
          <div className="flex items-baseline justify-between">
            <h2 className="text-base font-semibold tracking-tight">
              진료과목으로 둘러보기
            </h2>
            <p className="text-xs text-muted-foreground">
              위 검색창에 증상·시술을 입력하거나, 진료과목을 골라보세요
            </p>
          </div>
          <CategoryGrid
            specialties={specialtiesData?.data ?? []}
            totalHospitals={specialtiesData?.meta.total_hospitals ?? 0}
            onSelect={selectCategory}
            isLoading={specialtiesLoading}
          />
        </div>
      ) : (
        /* ── 목록: 카테고리/자연어 검색 결과 ── */
        <div className="space-y-4">
          {/* 헤더: 뒤로가기 + 제목 + 건수 */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <button
              type="button"
              onClick={backToBrowse}
              className="flex items-center gap-0.5 rounded-md px-1.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden />
              진료과목
            </button>
            <h2 className="text-lg font-semibold tracking-tight">{listTitle}</h2>
            {!isLoading ? (
              <span className="text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">{total}</span>곳
              </span>
            ) : null}
            <div className="ml-auto flex items-center gap-x-2 text-xs text-muted-foreground">
              {meta?.search_mode ? (
                <span>{SEARCH_MODE_LABEL[meta.search_mode] ?? meta.search_mode}</span>
              ) : null}
              {meta?.query_interpretation ? (
                <>
                  <span aria-hidden>·</span>
                  <span>해석: {meta.query_interpretation}</span>
                </>
              ) : null}
            </div>
          </div>

          <SearchFilters
            minConfidence={minConfidence}
            sort={sort}
            onMinConfidenceChange={setMinConfidence}
            onSortChange={setSort}
          />

          {/* 광고(협찬) 슬롯 — 자연 검색 결과와 분리. "광고" 라벨 명시 */}
          {ads.length > 0 ? (
            <div className="space-y-2">
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                스폰서
              </p>
              <ul className="grid gap-3">
                {ads.map((ad) => (
                  <li key={ad.ad_id}>
                    <AdCard ad={ad} />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* 카드 목록 */}
          {isError ? (
            <EmptyState
              message={`검색 중 오류가 발생했습니다 — ${
                (error as Error)?.message ?? "알 수 없는 오류"
              }`}
            />
          ) : isLoading ? (
            <ul className="grid gap-3">
              {[0, 1, 2, 3].map((i) => (
                <li
                  key={i}
                  className="animate-in fade-in duration-300"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  <HospitalCardSkeleton />
                </li>
              ))}
            </ul>
          ) : items.length === 0 ? (
            <EmptyState
              message={
                query
                  ? `"${query}" 에 해당하는 결과가 없습니다`
                  : specialty
                    ? `"${specialty}" 진료과목에 해당하는 결과가 없습니다 — 필터를 변경해보세요`
                    : "조건에 맞는 병원이 없습니다 — 근거 필터를 낮춰보세요"
              }
            />
          ) : (
            <>
              <ul className="grid gap-3">
                {items.map((item, i) => (
                  <li
                    key={item.hospital_id}
                    className="animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-300"
                    style={{ animationDelay: `${Math.min(i, 12) * 35}ms` }}
                  >
                    <HospitalCard item={item} />
                  </li>
                ))}
              </ul>

              <Pagination
                page={page}
                total={total}
                pageSize={PAGE_SIZE}
                onPage={setPage}
              />
            </>
          )}
        </div>
      )}
    </section>
  );
}
