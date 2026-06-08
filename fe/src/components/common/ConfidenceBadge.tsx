import { cn } from "@/lib/utils";
import type { Confidence, ConfidenceLevel } from "@/types/domain";

// 등급별 색상: 확실=에메랄드 / 추정=앰버 / 정보 부족=슬레이트
// (BE enum 키는 불변, 색상 매핑용)
const LEVEL_STYLE: Record<ConfidenceLevel, string> = {
  확실:
    "bg-confidence-high-50 text-confidence-high-700 border-confidence-high-100",
  추정:
    "bg-confidence-medium-50 text-confidence-medium-700 border-confidence-medium-100",
  "정보 부족":
    "bg-confidence-low-50 text-confidence-low-700 border-confidence-low-100",
};

// 표시 라벨 — "신뢰도"(병원 평가처럼 들림)가 아니라 *우리 분류가 몇 개 독립 출처로
// 뒷받침되나*(근거 강도)를 직관적으로. 의료법 §56 검수 통과 카피.
// BE enum(확실/추정/정보 부족)은 그대로 두고 표시만 치환.
// "자칭만 확인됨" → "병원 사이트 정보만 확인됨" (비전문가에게 더 명확)
const LEVEL_LABEL: Record<ConfidenceLevel, string> = {
  확실: "여러 출처가 일치",
  추정: "일부 출처로 확인",
  "정보 부족": "병원 사이트 정보만 확인됨",
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
      <span>{LEVEL_LABEL[confidence.level]}</span>
      {showScore ? (
        <span
          className="font-mono text-[11px] opacity-80"
          title={`근거 점수 ${confidence.score} / 100 — 출처가 많을수록 높음`}
          aria-label={`근거 점수 ${confidence.score}`}
        >
          {confidence.score}
        </span>
      ) : null}
    </span>
  );
}
