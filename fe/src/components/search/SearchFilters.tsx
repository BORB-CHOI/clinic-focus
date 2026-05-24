import { cn } from "@/lib/utils";
import type { SortOption } from "@/types/domain";

// API-FE-BE.md 검색 쿼리: min_confidence (기본 70), sort (distance/confidence/relevance)
// PoC 단계라 슬라이더 대신 의미 단위 토글 3개로 단순화
//
//   95+  → 확실만
//   70+  → 추정 이상 (기본)
//   0+   → 전체

export const MIN_CONFIDENCE_OPTIONS = [
  { value: 95, label: "확실만 (95+)" },
  { value: 70, label: "추정 이상 (70+)" },
  { value: 0, label: "전체" },
] as const;

export const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "distance", label: "거리순" },
  { value: "confidence", label: "신뢰도순" },
  { value: "relevance", label: "관련도순" },
];

interface SearchFiltersProps {
  minConfidence: number;
  sort: SortOption;
  onMinConfidenceChange: (value: number) => void;
  onSortChange: (value: SortOption) => void;
  className?: string;
}

// 검색 필터 — 카드 컨테이너 안에 신뢰도·정렬 두 그룹을 위계 있게 배치
// 라벨 → 칩 한 줄 구조로 굿닥/모두닥 필터 패널 톤에 맞춤
export function SearchFilters({
  minConfidence,
  sort,
  onMinConfidenceChange,
  onSortChange,
  className,
}: SearchFiltersProps) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-3 text-[0.85em]",
        className,
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6 sm:gap-y-2">
        <FilterGroup label="신뢰도">
          {MIN_CONFIDENCE_OPTIONS.map((option) => (
            <ToggleChip
              key={option.value}
              active={minConfidence === option.value}
              onClick={() => onMinConfidenceChange(option.value)}
            >
              {option.label}
            </ToggleChip>
          ))}
        </FilterGroup>

        <FilterGroup label="정렬">
          {SORT_OPTIONS.map((option) => (
            <ToggleChip
              key={option.value}
              active={sort === option.value}
              onClick={() => onSortChange(option.value)}
            >
              {option.label}
            </ToggleChip>
          ))}
        </FilterGroup>
      </div>
    </div>
  );
}

function FilterGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[0.85em] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <div className="flex flex-wrap gap-1">{children}</div>
    </div>
  );
}

function ToggleChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3 py-0.5 text-xs font-medium transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground shadow-sm"
          : "border-input bg-background text-muted-foreground hover:border-primary/40 hover:bg-accent hover:text-accent-foreground",
      )}
    >
      {children}
    </button>
  );
}
