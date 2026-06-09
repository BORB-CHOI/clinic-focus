import { cn } from "@/lib/utils";
import type { SortOption } from "@/types/domain";

// 검색 보조 컨트롤.
// "신뢰도"는 병원 평가가 아니라 *우리 분류를 몇 개 독립 출처가 뒷받침하나*(근거 강도)다.
// → 라벨을 '근거'로 리브랜딩. 그리고 기본은 '전체'(거르지 않음) — 근거로 검색을 하드
//   필터하면 관련 병원(출처 적은 곳)이 빠져 결과가 오히려 나빠지기 때문(신뢰도 ≠ 관련성).
//   좁히기는 사용자가 명시적으로 택할 때만.
export const MIN_CONFIDENCE_OPTIONS = [
  { value: 0, label: "전체" },
  { value: 70, label: "일부 출처 이상" },
  { value: 95, label: "여러 출처 일치만" },
] as const;

export const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "relevance", label: "관련도순" },
  { value: "distance", label: "거리순" },
  { value: "confidence", label: "근거 많은 순" },
  { value: "popular", label: "인기순" },
];

interface SearchFiltersProps {
  minConfidence: number;
  sort: SortOption;
  onMinConfidenceChange: (value: number) => void;
  onSortChange: (value: SortOption) => void;
  className?: string;
  // ── 심평원 전문의 필터 (카테고리 탐색 맥락에서만 노출) ─────────────────
  /**
   * true 면 심평원 전문의 필터 UI 를 표시.
   * 자연어 q 있는 화면에서는 false 로 전달(토글 자체를 숨김).
   * 기본값 false.
   */
  showHiraFilter?: boolean;
  /** 현재 심평원 전문의 필터 상태 */
  hasSpecialist?: boolean;
  onHasSpecialistChange?: (value: boolean) => void;
}

// 검색 필터 — 카드 컨테이너 안에 신뢰도·정렬 두 그룹을 위계 있게 배치
// 라벨 → 칩 한 줄 구조로 굿닥/모두닥 필터 패널 톤에 맞춤
//
// 심평원 전문의 필터 (showHiraFilter=true 일 때만 노출):
//   - 카테고리/시군구 탐색 맥락에서만 표시.
//   - 자연어 q 있는 화면에선 숨겨 혼동 방지(q 있으면 BE 가 무시).
//   - 현재 키 미승인으로 has_specialist=true 시 결과 0건 가능 → 보조문구로 안내.
export function SearchFilters({
  minConfidence,
  sort,
  onMinConfidenceChange,
  onSortChange,
  className,
  showHiraFilter = false,
  hasSpecialist = false,
  onHasSpecialistChange,
}: SearchFiltersProps) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-3 text-[0.85em]",
        className,
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6 sm:gap-y-2">
        <FilterGroup label="근거">
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

        {/* 심평원 전문의 필터 — 카테고리 탐색 맥락에서만 노출 */}
        {showHiraFilter && onHasSpecialistChange && (
          <FilterGroup label="심평원 신고">
            <ToggleChip
              active={hasSpecialist}
              onClick={() => onHasSpecialistChange(!hasSpecialist)}
            >
              전문의 신고 있는 곳만
            </ToggleChip>
          </FilterGroup>
        )}
      </div>

      {minConfidence > 0 ? (
        <p className="mt-2 text-[0.8em] leading-relaxed text-muted-foreground">
          ⓘ 출처가 적은 병원이 빠져 결과가 줄어듭니다. '근거'는 병원 평가가 아니라 우리 분류를
          뒷받침하는 독립 출처(병원 사이트·이미지 분석·블로그·후기) 수예요.
        </p>
      ) : null}

      {/* 심평원 필터 활성 시 보조 안내 — 키 미승인으로 현재 결과가 줄어들 수 있음 */}
      {showHiraFilter && hasSpecialist && (
        <p className="mt-2 text-[0.8em] leading-relaxed text-muted-foreground">
          ⓘ 심평원 신고 데이터 연동 준비 중으로, 현재 결과가 적게 나올 수 있습니다.
          신고 데이터는 병원이 심평원에 제출한 수치를 기준으로 합니다.
        </p>
      )}
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
