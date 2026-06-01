import { cn } from "@/lib/utils";
import type { ConfidenceLevel } from "@/types/domain";

// 마커 색상 = ConfidenceBadge 와 같은 토큰 (확실=에메랄드 / 추정=앰버 /
// 정보 부족=슬레이트). 사용자가 마커 색을 즉시 해석할 수 있도록 지도 옆에 노출
// label = ConfidenceBadge 와 동일 카피(병원 평가 아닌 '근거 출처 수'). §56 검수 통과.
const ITEMS: { level: ConfidenceLevel; label: string; dotClass: string; ringClass: string }[] = [
  {
    level: "확실",
    label: "여러 출처 일치",
    dotClass: "bg-confidence-high-500",
    ringClass: "ring-confidence-high-100",
  },
  {
    level: "추정",
    label: "일부 출처 확인",
    dotClass: "bg-confidence-medium-500",
    ringClass: "ring-confidence-medium-100",
  },
  {
    level: "정보 부족",
    label: "자칭만 확인",
    dotClass: "bg-confidence-low-500",
    ringClass: "ring-confidence-low-100",
  },
];

export function ConfidenceLegend({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-3 gap-y-1 text-xs",
        className,
      )}
    >
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        마커
      </span>
      {ITEMS.map((item) => (
        <span key={item.level} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn(
              "inline-block h-2.5 w-2.5 rounded-full ring-2",
              item.dotClass,
              item.ringClass,
            )}
          />
          <span className="text-muted-foreground">{item.label}</span>
        </span>
      ))}
    </div>
  );
}
