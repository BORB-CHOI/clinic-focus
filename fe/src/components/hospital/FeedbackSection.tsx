import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ThumbsDown, ThumbsUp, User } from "lucide-react";

import { Section } from "@/components/common/Section";
import { Button } from "@/components/ui/button";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";
import { getDeviceId } from "@/lib/device";
import type { FeedbackStats } from "@/types/domain";

const AGE_LABEL: Record<string, string> = {
  teens: "10대", "20s": "20대", "30s": "30대",
  "40s": "40대", "50plus": "50대 이상",
};
const GENDER_LABEL: Record<string, string> = {
  male: "남성", female: "여성",
};

interface ProfileData { gender_bucket: string; age_bucket: string }

interface ReviewItem {
  verdict: "agree" | "disagree";
  review_text: string;
  age_bucket: string | null;
  gender_bucket: string | null;
  received_at: string;
}

interface FeedbackSectionProps {
  hospitalId: string;
  primary_focus: string[];
  feedback_stats: FeedbackStats;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function FeedbackSection({
  hospitalId,
  primary_focus,
  feedback_stats,
}: FeedbackSectionProps) {
  const deviceId = getDeviceId();

  // 사용자 프로필
  const { data: profileRes } = useQuery<{ data: ProfileData } | null>({
    queryKey: ["analytics-profile", deviceId],
    queryFn: ({ signal }) =>
      apiGet<{ data: ProfileData }>("/api/analytics/profile", { device_id: deviceId }, signal)
        .catch(() => null),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  // 최신 통계 + 리뷰 목록 (제출 후 갱신)
  const [statsVersion, setStatsVersion] = useState(0);
  const { data: freshStats } = useQuery<{
    data: FeedbackStats & { recent_reviews?: ReviewItem[] }
  }>({
    queryKey: ["feedback-stats", hospitalId, statsVersion],
    queryFn: ({ signal }) =>
      apiGet<{ data: FeedbackStats & { recent_reviews?: ReviewItem[] } }>(
        `/api/feedback/${hospitalId}/stats`, {}, signal,
      ),
    staleTime: 0,
    retry: false,
  });

  const profile = profileRes?.data ?? null;
  const cohortLabel = profile
    ? `${AGE_LABEL[profile.age_bucket] ?? profile.age_bucket} ${GENDER_LABEL[profile.gender_bucket] ?? ""}`
    : null;

  // 동의/반대 상태
  const [verdictDone, setVerdictDone] = useState<"agree" | "disagree" | null>(null);
  const [stats, setStats] = useState(feedback_stats);

  // 후기 상태
  const [reviewText, setReviewText] = useState("");
  const [reviewDone, setReviewDone] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const displayStats = freshStats?.data ?? stats;
  const recentReviews: ReviewItem[] = (freshStats?.data as { recent_reviews?: ReviewItem[] } | undefined)?.recent_reviews ?? [];
  const ratioPct = Math.round(displayStats.agree_ratio * 100);
  const target = primary_focus[0] ?? "현재 분류";

  // ── 동의/반대 제출 ─────────────────────────────────────────────────────
  function handleVerdict(verdict: "agree" | "disagree") {
    if (verdictDone) return;
    const next = { ...stats };
    next.total_count += 1;
    if (verdict === "agree") next.agree_count += 1;
    else next.disagree_count += 1;
    next.agree_ratio = next.agree_count / next.total_count;
    next.last_feedback_at = new Date().toISOString();
    setStats(next);
    setVerdictDone(verdict);

    fetch(`${API_BASE}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hospital_id: hospitalId,
        device_id: deviceId,
        primary_focus: primary_focus[0] ?? "",
        verdict,
        age_bucket: profile?.age_bucket ?? null,
        gender_bucket: profile?.gender_bucket ?? null,
      }),
    })
      .then(() => setStatsVersion((v) => v + 1))
      .catch(() => {});
  }

  // ── 후기 제출 ─────────────────────────────────────────────────────────
  function handleReviewSubmit() {
    const text = reviewText.trim();
    if (!text || reviewDone) return;
    setReviewDone(true);

    fetch(`${API_BASE}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hospital_id: hospitalId,
        device_id: `${deviceId}_r`,   // review 전용 suffix — verdict duplicate 와 분리
        primary_focus: primary_focus[0] ?? "",
        verdict: verdictDone ?? "agree",
        review_text: text,
        age_bucket: profile?.age_bucket ?? null,
        gender_bucket: profile?.gender_bucket ?? null,
      }),
    })
      .then(() => setStatsVersion((v) => v + 1))
      .catch(() => {});
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
          적절한지 평가하고 후기를 남겨주세요
        </>
      }
    >
      <div className="space-y-4">
      {/* 프로필 레이블 */}
      {cohortLabel && (
        <div className="flex items-center gap-1.5 rounded-md bg-primary/5 border border-primary/15 px-3 py-2 text-xs text-primary">
          <User className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span><span className="font-semibold">{cohortLabel}</span>으로 참여하고 있어요</span>
        </div>
      )}

      {/* 누적 비율 막대 */}
      <div className="rounded-md border bg-background p-3">
        <div className="mb-2 flex items-baseline justify-between gap-2 text-xs">
          <span className="text-confidence-high-700">
            <span className="font-semibold">동의 {ratioPct}%</span>
            <span className="ml-1 text-muted-foreground">({displayStats.agree_count}건)</span>
          </span>
          <span className="text-muted-foreground">
            반대 {100 - ratioPct}% ({displayStats.disagree_count}건)
          </span>
        </div>
        <div className="flex h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full bg-confidence-high-500 transition-all" style={{ width: `${ratioPct}%` }} />
          <div className="h-full bg-confidence-low-100 transition-all" style={{ width: `${100 - ratioPct}%` }} />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          누적 {displayStats.total_count}건
          {displayStats.last_feedback_at && (
            <> · 마지막 피드백 {new Date(displayStats.last_feedback_at).toLocaleDateString("ko-KR")}</>
          )}
        </p>
      </div>

      {/* 동의/반대 버튼 */}
      <div className="grid grid-cols-2 gap-2">
        <Button
          variant={verdictDone === "agree" ? "default" : "outline"}
          onClick={() => handleVerdict("agree")}
          disabled={verdictDone !== null}
          aria-pressed={verdictDone === "agree"}
          size="lg"
          className={cn("h-12", verdictDone === "agree" && "bg-confidence-high-500 hover:bg-confidence-high-700")}
        >
          <ThumbsUp className="h-5 w-5" />
          맞아요
        </Button>
        <Button
          variant={verdictDone === "disagree" ? "destructive" : "outline"}
          onClick={() => handleVerdict("disagree")}
          disabled={verdictDone !== null}
          aria-pressed={verdictDone === "disagree"}
          size="lg"
          className="h-12"
        >
          <ThumbsDown className="h-5 w-5" />
          아니에요
        </Button>
      </div>

      {verdictDone ? (
        <p className="inline-flex items-center gap-1.5 text-xs text-confidence-high-700">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
          <span>피드백을 받았습니다 — 같은 디바이스에서 한 번만 제출됩니다</span>
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">익명 · 로그인 없이 1초 안에</p>
      )}

      {/* ── 후기 작성란 (항상 노출) ── */}
      <div className="space-y-2 border-t pt-4">
        <p className="text-xs font-semibold text-foreground">후기 남기기</p>
        {!reviewDone ? (
          <>
            <textarea
              ref={textareaRef}
              value={reviewText}
              onChange={(e) => setReviewText(e.target.value.slice(0, 200))}
              placeholder="예: 감기 진료 잘해주시네요. 친절하고 좋아요."
              rows={3}
              className="w-full rounded-md border bg-background px-3 py-2 text-xs placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary resize-none"
            />
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">{reviewText.length}/200</span>
              <button
                type="button"
                onClick={handleReviewSubmit}
                disabled={!reviewText.trim()}
                className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-40 hover:opacity-90 transition-opacity"
              >
                등록하기
              </button>
            </div>
          </>
        ) : (
          <p className="inline-flex items-center gap-1.5 text-xs text-confidence-high-700">
            <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
            후기가 등록됐어요
          </p>
        )}
      </div>

      {/* ── 다른 사용자 후기 ── */}
      {recentReviews.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-muted-foreground">방문자 후기</p>
          <ul className="space-y-2">
            {recentReviews.map((r, i) => {
              const age = r.age_bucket ? (AGE_LABEL[r.age_bucket] ?? r.age_bucket) : null;
              const gender = r.gender_bucket ? (GENDER_LABEL[r.gender_bucket] ?? "") : null;
              const who = age && gender ? `${age} ${gender}` : age ?? gender ?? "익명";
              return (
                <li key={i} className="rounded-md border bg-muted/30 px-3 py-2.5 space-y-1">
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground flex-wrap">
                    <span className="font-medium text-foreground">{who}</span>
                    <span aria-hidden>·</span>
                    <span className={cn(
                      "font-medium",
                      r.verdict === "agree" ? "text-confidence-high-700" : "text-confidence-low-700",
                    )}>
                      {r.verdict === "agree" ? "분류 맞아요" : "분류 아니에요"}
                    </span>
                    <span aria-hidden>·</span>
                    <span>{new Date(r.received_at).toLocaleDateString("ko-KR")}</span>
                  </div>
                  <p className="text-xs text-foreground leading-relaxed">{r.review_text}</p>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      </div>
    </Section>
  );
}
