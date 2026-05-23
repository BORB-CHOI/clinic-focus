import { useState } from "react";
import { ThumbsUp, ThumbsDown } from "lucide-react";

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
// 익명 + localStorage device_id 기반 1-tap 평가
// BE 연동 전까지는 낙관적 업데이트만 (POST /api/feedback 연결은 다음 단계)
export function FeedbackSection({
  hospitalId,
  primary_focus,
  feedback_stats,
}: FeedbackSectionProps) {
  const [submitted, setSubmitted] = useState<"agree" | "disagree" | null>(null);
  const [stats, setStats] = useState(feedback_stats);

  const ratioPct = Math.round(stats.agree_ratio * 100);

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

  const target = primary_focus[0] ?? "현재 분류";

  return (
    <Section
      id="section-feedback"
      title="사용자 피드백"
      badge="⑥"
      subtitle={`이 병원의 분류 "${target}"가 적절한지 1-tap으로 평가`}
    >
      <div className="flex items-center gap-4">
        <Button
          variant={submitted === "agree" ? "default" : "outline"}
          onClick={() => handleSubmit("agree")}
          disabled={submitted !== null}
          aria-pressed={submitted === "agree"}
        >
          <ThumbsUp className="h-4 w-4" />
          맞아요 ({stats.agree_count})
        </Button>
        <Button
          variant={submitted === "disagree" ? "destructive" : "outline"}
          onClick={() => handleSubmit("disagree")}
          disabled={submitted !== null}
          aria-pressed={submitted === "disagree"}
        >
          <ThumbsDown className="h-4 w-4" />
          아니에요 ({stats.disagree_count})
        </Button>
      </div>

      <p
        className={cn(
          "mt-4 text-sm",
          submitted ? "text-foreground" : "text-muted-foreground",
        )}
      >
        {submitted
          ? "피드백을 받았습니다. 같은 디바이스에서 한 번만 제출됩니다."
          : `누적 ${stats.total_count}건 · 동의 비율 ${ratioPct}%`}
      </p>
    </Section>
  );
}
