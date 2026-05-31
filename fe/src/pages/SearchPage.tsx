import { useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";
import { HospitalCard } from "@/components/search/HospitalCard";
import { HospitalCardSkeleton } from "@/components/search/HospitalCardSkeleton";
import { SearchFilters } from "@/components/search/SearchFilters";
import { useSearch } from "@/hooks/useSearch";
import type { SortOption } from "@/types/domain";

// 검색 결과 페이지 — BE /api/search 연동 (useSearch hook)
//
// q·min_confidence·sort 를 URL 쿼리스트링에 묶어 새로고침·뒤로가기·공유에서 상태 보존.
// 검색/필터/정렬은 모두 BE 가 서버사이드 처리 (q 있으면 KB 자연어, 없으면 강남 카테고리).
// 기본 신뢰도 필터는 0(전체) — BE 기본값(차별노출 회피)과 일치, 신호 적은 병원도 노출.

const SEARCH_MODE_LABEL: Record<string, string> = {
  natural: "자연어",
  nearby: "근처",
  "natural+nearby": "자연어+근처",
  category: "카테고리",
};

const SORT_LABEL: Record<SortOption, string> = {
  distance: "거리순",
  confidence: "신뢰도순",
  relevance: "관련도순",
};

const VALID_SORTS: SortOption[] = ["distance", "confidence", "relevance"];

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const query = searchParams.get("q") ?? "";

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

  const setMinConfidence = (value: number) => {
    const next = new URLSearchParams(searchParams);
    if (value === 0) next.delete("min_confidence");
    else next.set("min_confidence", String(value));
    setSearchParams(next, { replace: true });
  };
  const setSort = (value: SortOption) => {
    const next = new URLSearchParams(searchParams);
    if (value === "relevance") next.delete("sort");
    else next.set("sort", value);
    setSearchParams(next, { replace: true });
  };

  const { data, isLoading, isError, error } = useSearch({
    q: query,
    minConfidence,
    sort,
  });

  const items = data?.data ?? [];
  const meta = data?.meta;
  const total = meta?.total ?? items.length;

  return (
    <section className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">병원 검색</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          표준 진료과목 너머, 이 병원이 자기 사이트에서 무엇을 메인으로
          표시하는지를 보여줍니다.
        </p>
      </div>

      <SearchFilters
        minConfidence={minConfidence}
        sort={sort}
        onMinConfidenceChange={setMinConfidence}
        onSortChange={setSort}
      />

      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b pb-2 text-xs text-muted-foreground">
        <p>
          <span className="text-base font-semibold text-foreground">
            {total}
          </span>
          <span className="ml-1">건</span>
          {query ? (
            <span className="ml-2 text-muted-foreground">
              "{query}" 검색 결과
            </span>
          ) : null}
        </p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {meta?.search_mode ? (
            <span>{SEARCH_MODE_LABEL[meta.search_mode] ?? meta.search_mode}</span>
          ) : null}
          <span aria-hidden>·</span>
          <span>{SORT_LABEL[sort]}</span>
          {meta?.query_interpretation ? (
            <>
              <span aria-hidden>·</span>
              <span>해석: {meta.query_interpretation}</span>
            </>
          ) : null}
        </div>
      </div>

      {isError ? (
        <EmptyState
          message={`검색 중 오류가 발생했습니다 — ${
            (error as Error)?.message ?? "알 수 없는 오류"
          }`}
        />
      ) : isLoading ? (
        <ul className="grid gap-3">
          {[0, 1, 2, 3].map((i) => (
            <li key={i}>
              <HospitalCardSkeleton />
            </li>
          ))}
        </ul>
      ) : items.length === 0 ? (
        <EmptyState
          message={
            query
              ? `"${query}" 에 해당하는 결과가 없습니다`
              : "조건에 맞는 병원이 없습니다 — 신뢰도 필터를 낮춰보세요"
          }
        />
      ) : (
        <ul className="grid gap-3">
          {items.map((item) => (
            <li key={item.hospital_id}>
              <HospitalCard item={item} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
