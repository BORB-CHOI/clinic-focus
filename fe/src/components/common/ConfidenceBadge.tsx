import { cn } from "@/lib/utils";
import type { Confidence, ConfidenceLevel } from "@/types/domain";

// 신뢰도 등급별 색상: 확실=에메랄드 / 추정=앰버 / 정보 부족=슬레이트
// (모던 SaaS 톤. 4단계 스케일 50/100/500/700 의 의미 매핑은 tailwind.config.js 참조)
const LEVEL_STYLE: Record<ConfidenceLevel, string> = {
  확실:
    "bg-confidence-high-50 text-confidence-high-700 border-confidence-high-100",
  추정:
    "bg-confidence-medium-50 text-confidence-medium-700 border-confidence-medium-100",
  "정보 부족":
    "bg-confidence-low-50 text-confidence-low-700 border-confidence-low-100",
};

interface ConfidenceBadgeProps {
  confidence: Pick<Confidence, "level" | "score">;
  showScore?: boolean;
  className?: string;
}

export function ConfidenceBadge({
  confidence,
  showScore = true,
  className,
}: ConfidenceBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        LEVEL_STYLE[confidence.level],
        className,
      )}
    >
      <span aria-hidden>●</span>
      <span>{confidence.level}</span>
      {showScore ? (
        <span className="font-mono text-[11px] opacity-80">
          {confidence.score}
        </span>
      ) : null}
    </span>
  );
}
