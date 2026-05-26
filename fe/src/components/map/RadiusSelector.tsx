import { cn } from "@/lib/utils";

// API-FE-BE.md: radius_km 기본 3, 최대 30
// PoC 단계에선 overview.md 가 정한 5단계 토글 (0.5/1/3/5/10)
export const RADIUS_OPTIONS = [0.5, 1, 3, 5, 10] as const;
export type RadiusKm = (typeof RADIUS_OPTIONS)[number];

interface RadiusSelectorProps {
  value: RadiusKm;
  onChange: (value: RadiusKm) => void;
  className?: string;
}

export function RadiusSelector({
  value,
  onChange,
  className,
}: RadiusSelectorProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        반경
      </span>
      <div
        role="radiogroup"
        aria-label="검색 반경"
        className="inline-flex items-center gap-0.5 rounded-full border bg-card p-0.5"
      >
        {RADIUS_OPTIONS.map((km) => (
          <button
            key={km}
            type="button"
            onClick={() => onChange(km)}
            role="radio"
            aria-checked={value === km}
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
              value === km
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            {km < 1 ? `${km * 1000}m` : `${km}km`}
          </button>
        ))}
      </div>
    </div>
  );
}
