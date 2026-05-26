import { useState } from "react";
import { ThumbsUp, ThumbsDown, CheckCircle2 } from "lucide-react";

import { Section } from "@/components/common/Section";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getDeviceId } from "@/lib/device";
import type { FeedbackStats } from "@/types/domain";

interface FeedbackSectionProps {
  hospitalId: string;
  primary_focus: string[];
  feedback_stats: FeedbackStats;
}

// ⑥ 사용자 피드백
//
// 평가요소 "사용자 피드백 루프" 의 시각화 영역. 1-tap 제출 + 누적 비율 막대.
// 익명 + localStorage device_id 기반 — BE 연동 전까진 낙관적 업데이트만.
export function FeedbackSection({
  hospitalId,
  primary_focus,
  feedback_stats,
}: FeedbackSectionProps) {
  const [submitted, setSubmitted] = useState<"agree" | "disagree" | null>(null);
  const [stats, setStats] = useState(feedback_stats);

  const ratioPct = Math.round(stats.agree_ratio * 100);
  const target = primary_focus[0] ?? "현재 분류";

  function handleSubmit(verdict: "agree" | "disagree") {
    if (submitted) return;
    // TODO(api): POST /api/feedback (device_id, hospital_id, primary_focus, verdict)
    // 409 DUPLICATE_FEEDBACK 처리 포함. 지금은 낙관적 업데이트만.
    void getDeviceId();
    void hospitalId;

    const next = { ...stats };
    next.total_count += 1;
    if (verdict === "agree") next.agree_count += 1;
    else next.disagree_count += 1;
    next.agree_ratio = next.agree_count / next.total_count;
    next.last_feedback_at = new Date().toISOString();

    setStats(next);
    setSubmitted(verdict);
  }

  return (
    <Section
      id="section-feedback"
      title="사용자 피드백"
      badge="⑥"
      subtitle={
        <>
          이 병원의 분류{" "}
          <span className="font-semibold text-foreground">"{target}"</span>가
          적절한지 1-tap 으로 평가해 주세요
        </>
      }
    >
      {/* 누적 비율 막대 — 동의/반대 좌우 분할 */}
      <div className="rounded-md border bg-background p-3">
        <div className="mb-2 flex items-baseline justify-between gap-2 text-xs">
          <span className="text-confidence-high-700">
            <span className="font-semibold">동의 {ratioPct}%</span>
            <span className="ml-1 text-muted-foreground">
              ({stats.agree_count}건)
            </span>
          </span>
          <span className="text-confidence-low-700">
            <span className="text-muted-foreground">
              반대 {100 - ratioPct}% ({stats.disagree_count}건)
            </span>
          </span>
        </div>
        <div className="flex h-2 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full bg-confidence-high-500 transition-all"
            style={{ width: `${ratioPct}%` }}
            aria-label={`동의 ${ratioPct}%`}
          />
          <div
            className="h-full bg-confidence-low-100 transition-all"
            style={{ width: `${100 - ratioPct}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          누적 {stats.total_count}건
          {stats.last_feedback_at ? (
            <>
              {" · "}
              마지막 피드백{" "}
              {new Date(stats.last_feedback_at).toLocaleDateString("ko-KR")}
            </>
          ) : null}
        </p>
      </div>

      {/* 1-tap 버튼 */}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <Button
          variant={submitted === "agree" ? "default" : "outline"}
          onClick={() => handleSubmit("agree")}
          disabled={submitted !== null}
          aria-pressed={submitted === "agree"}
          size="lg"
          className={cn(
            "h-12",
            submitted === "agree" &&
              "bg-confidence-high-500 hover:bg-confidence-high-700",
          )}
        >
          <ThumbsUp className="h-5 w-5" />
          맞아요
        </Button>
        <Button
          variant={submitted === "disagree" ? "destructive" : "outline"}
          onClick={() => handleSubmit("disagree")}
          disabled={submitted !== null}
          aria-pressed={submitted === "disagree"}
          size="lg"
          className="h-12"
        >
          <ThumbsDown className="h-5 w-5" />
          아니에요
        </Button>
      </div>

      {submitted ? (
        <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-confidence-high-700">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
          <span>피드백을 받았습니다 — 같은 디바이스에서 한 번만 제출됩니다</span>
        </p>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">
          익명 · 로그인 없이 1초 안에
        </p>
      )}
    </Section>
  );
}
