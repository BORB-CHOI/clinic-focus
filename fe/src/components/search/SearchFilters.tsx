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
        "flex flex-wrap items-center gap-x-6 gap-y-3 text-sm",
        className,
      )}
    >
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
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-muted-foreground">
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
        "rounded-full border px-2.5 py-0.5 text-xs transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-input bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
      {children}
    </button>
  );
}
