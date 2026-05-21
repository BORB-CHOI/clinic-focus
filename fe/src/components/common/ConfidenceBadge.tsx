import { cn } from "@/lib/utils";
import type { Confidence, ConfidenceLevel } from "@/types/domain";

// 신뢰도 등급별 색상: 확실=초록 / 추정=노랑 / 정보 부족=회색 (fe/CLAUDE.md 명시)
const LEVEL_STYLE: Record<ConfidenceLevel, string> = {
  확실: "bg-confidence-high/15 text-confidence-high border-confidence-high/30",
  추정: "bg-confidence-medium/15 text-confidence-medium border-confidence-medium/40",
  "정보 부족":
    "bg-confidence-low/15 text-confidence-low border-confidence-low/30",
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
