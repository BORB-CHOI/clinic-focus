import { useMemo, useState } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { HospitalCard } from "@/components/search/HospitalCard";
import { SearchInput } from "@/components/search/SearchInput";
import { SearchFilters } from "@/components/search/SearchFilters";
import { mockSearchResponse } from "@/mocks/searchResults";
import type { SearchResultItem, SortOption } from "@/types/domain";

// 검색 결과 페이지 — Mock 데이터로 카드 리스트 구성
//
// BE 연동(5단계)은 아직. fetch 없이 mockSearchResponse를 직접 import 해서
// 클라이언트 사이드에서 단순 필터·정렬만 적용한다.
// 5단계에서 useQuery({ queryKey: ['search', q, minConfidence, sort], queryFn: fetch... })
// 로 갈아끼울 때 본 컴포넌트 구조는 그대로 유지하면 된다.

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
      // distance_km null인 항목은 뒤로 보냄
      return copy.sort((a, b) => {
        const da = a.distance_km ?? Number.POSITIVE_INFINITY;
        const db = b.distance_km ?? Number.POSITIVE_INFINITY;
        return da - db;
      });
    case "confidence":
      return copy.sort((a, b) => b.confidence.score - a.confidence.score);
    case "relevance":
      // 자연어 매칭 강도는 BE의 RAG가 결정. 클라에서는 원본 순서 유지
      return copy;
  }
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [minConfidence, setMinConfidence] = useState(70);
  const [sort, setSort] = useState<SortOption>("distance");

  const filtered = useMemo(() => {
    const matched = mockSearchResponse.data.filter(
      (item) =>
        item.confidence.score >= minConfidence && matchesQuery(item, query),
    );
    return applySort(matched, sort);
  }, [query, minConfidence, sort]);

  const baseMeta = mockSearchResponse.meta;

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">병원 검색</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          표준 진료과목 너머, 이 병원이 자기 사이트에서 무엇을 메인으로
          표시하는지를 보여줍니다.
        </p>
      </div>

      <SearchInput onSearch={setQuery} />

      <SearchFilters
        minConfidence={minConfidence}
        sort={sort}
        onMinConfidenceChange={setMinConfidence}
        onSortChange={setSort}
      />

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span>
          <span className="font-semibold text-foreground">
            {filtered.length}
          </span>
          건
        </span>
        <span aria-hidden>·</span>
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
