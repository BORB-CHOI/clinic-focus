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
    <div className={cn("flex items-center gap-2 text-sm", className)}>
      <span className="text-xs font-medium text-muted-foreground">반경</span>
      <div className="flex flex-wrap gap-1">
        {RADIUS_OPTIONS.map((km) => (
          <button
            key={km}
            type="button"
            onClick={() => onChange(km)}
            aria-pressed={value === km}
            className={cn(
              "rounded-full border px-2.5 py-0.5 text-xs transition-colors",
              value === km
                ? "border-primary bg-primary text-primary-foreground"
                : "border-input bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground",
            )}
          >
            {km < 1 ? `${km * 1000}m` : `${km}km`}
          </button>
        ))}
      </div>
    </div>
  );
}
