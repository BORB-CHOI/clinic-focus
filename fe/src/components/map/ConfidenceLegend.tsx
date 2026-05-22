import { cn } from "@/lib/utils";
import type { ConfidenceLevel } from "@/types/domain";

// 마커 색상 = ConfidenceBadge 와 같은 토큰 (확실/추정/정보 부족)
// 사용자가 마커 색을 바로 해석할 수 있도록 지도 옆에 작게 노출
const ITEMS: { level: ConfidenceLevel; dotClass: string }[] = [
  { level: "확실", dotClass: "bg-confidence-high" },
  { level: "추정", dotClass: "bg-confidence-medium" },
  { level: "정보 부족", dotClass: "bg-confidence-low" },
];

export function ConfidenceLegend({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border bg-card px-3 py-1.5 text-xs",
        className,
      )}
    >
      <span className="text-muted-foreground">마커 색</span>
      {ITEMS.map((item) => (
        <span key={item.level} className="flex items-center gap-1">
          <span
            aria-hidden
            className={cn("inline-block h-2.5 w-2.5 rounded-full", item.dotClass)}
          />
          <span>{item.level}</span>
        </span>
      ))}
    </div>
  );
}
