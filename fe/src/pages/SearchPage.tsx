import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";
import { HospitalCard } from "@/components/search/HospitalCard";
import { SearchFilters } from "@/components/search/SearchFilters";
import { mockSearchResponse } from "@/mocks/searchResults";
import type { SearchResultItem, SortOption } from "@/types/domain";

// 검색 결과 페이지 — Mock 데이터로 카드 리스트 구성
//
// 검색어 q 와 필터(min_confidence, sort) 모두 URL 쿼리스트링에 묶었다.
//   - q                : 글로벌 셸의 StickySearchBar 가 디바운스로 갱신
//   - min_confidence   : SearchFilters 토글이 갱신
//   - sort             : 동
// 새로고침·뒤로가기·공유에서 상태 보존, 5단계 BE 연동 시 useQuery 키도
// 그대로 URL 파라미터로 매핑하면 된다.

const SEARCH_MODE_LABEL: Record<string, string> = {
  natural: "자연어",
  nearby: "근처",
  "natural+nearby": "자연어+근처",
};

const SORT_LABEL: Record<SortOption, string> = {
  distance: "거리순",
  confidence: "신뢰도순",
  relevance: "관련도순",
};

const VALID_SORTS: SortOption[] = ["distance", "confidence", "relevance"];

function matchesQuery(item: SearchResultItem, q: string): boolean {
  if (!q) return true;
  const needle = q.toLowerCase();
  const haystack = [
    item.name,
    item.one_line_summary,
    item.standard_specialty,
    ...item.primary_focus,
    item.location.sigungu,
    item.location.dong ?? "",
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

function applySort(
  items: SearchResultItem[],
  sort: SortOption,
): SearchResultItem[] {
  const copy = [...items];
  switch (sort) {
    case "distance":
      return copy.sort((a, b) => {
        const da = a.distance_km ?? Number.POSITIVE_INFINITY;
        const db = b.distance_km ?? Number.POSITIVE_INFINITY;
        return da - db;
      });
    case "confidence":
      return copy.sort((a, b) => b.confidence.score - a.confidence.score);
    case "relevance":
      return copy;
  }
}

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const query = searchParams.get("q") ?? "";

  const minConfidenceParam = Number.parseInt(
    searchParams.get("min_confidence") ?? "70",
    10,
  );
  const minConfidence = Number.isFinite(minConfidenceParam)
    ? minConfidenceParam
    : 70;

  const sortParam = searchParams.get("sort") as SortOption | null;
  const sort: SortOption = VALID_SORTS.includes(sortParam ?? ("" as SortOption))
    ? (sortParam as SortOption)
    : "distance";

  const setMinConfidence = (value: number) => {
    const next = new URLSearchParams(searchParams);
    if (value === 70) next.delete("min_confidence");
    else next.set("min_confidence", String(value));
    setSearchParams(next, { replace: true });
  };
  const setSort = (value: SortOption) => {
    const next = new URLSearchParams(searchParams);
    if (value === "distance") next.delete("sort");
    else next.set("sort", value);
    setSearchParams(next, { replace: true });
  };

  const filtered = useMemo(() => {
    const matched = mockSearchResponse.data.filter(
      (item) =>
        item.confidence.score >= minConfidence && matchesQuery(item, query),
    );
    return applySort(matched, sort);
  }, [query, minConfidence, sort]);

  const baseMeta = mockSearchResponse.meta;

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
            {filtered.length}
          </span>
          <span className="ml-1">건</span>
          {query ? (
            <span className="ml-2 text-muted-foreground">
              "{query}" 검색 결과
            </span>
          ) : null}
        </p>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span>{SEARCH_MODE_LABEL[baseMeta.search_mode] ?? baseMeta.search_mode}</span>
          <span aria-hidden>·</span>
          <span>{SORT_LABEL[sort]}</span>
          {baseMeta.query_interpretation ? (
            <>
              <span aria-hidden>·</span>
              <span>해석: {baseMeta.query_interpretation}</span>
            </>
          ) : null}
          {baseMeta.radius_km !== null ? (
            <>
              <span aria-hidden>·</span>
              <span>반경 {baseMeta.radius_km}km</span>
            </>
          ) : null}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          message={
            query
              ? `"${query}" 에 해당하는 결과가 없습니다`
              : "조건에 맞는 병원이 없습니다 — 신뢰도 필터를 낮춰보세요"
          }
        />
      ) : (
        <ul className="grid gap-3">
          {filtered.map((item) => (
            <li key={item.hospital_id}>
              <HospitalCard item={item} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
