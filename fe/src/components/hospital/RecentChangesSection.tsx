import { ArrowRight, ExternalLink } from "lucide-react";

import { Section } from "@/components/common/Section";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ChangeReason, ClassificationChange } from "@/types/domain";

const REASON_LABEL: Record<ChangeReason, string> = {
  feedback_accumulated: "피드백 누적",
  human_review: "수동 검수",
  vision_reanalysis: "Vision 재분석",
  scheduled_recrawl: "정기 재수집",
};

interface RecentChangesSectionProps {
  hospitalId: string;
  recent_changes: ClassificationChange[];
}

// ⑦ 분류 변경 이력 — 평가요소 "투명성" 핵심 영역
//
// 시간 흐름을 인지하도록 좌측 세로 점선 + 노드 점 + from→to 카피로 타임라인 구성.
// 가장 최근 변경에는 강조 톤(primary)으로 시각 우선순위.
export function RecentChangesSection({
  hospitalId,
  recent_changes,
}: RecentChangesSectionProps) {
  return (
    <Section
      id="section-recent-changes"
      title="분류 변경 이력"
      badge="⑦"
      subtitle="이 병원의 주력 분류가 시간에 따라 어떻게 바뀌었는지"
      action={
        recent_changes.length > 0 ? (
          <a
            href={`/api/hospitals/${hospitalId}/history`}
            className="inline-flex items-center gap-1 text-sm text-primary underline-offset-2 hover:underline"
          >
            전체 이력
            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          </a>
        ) : null
      }
    >
      {recent_changes.length === 0 ? (
        <EmptyState message="변경 이력 없음" />
      ) : (
        <ol className="relative ml-4 space-y-4 border-l-2 border-dashed border-border pl-6">
          {recent_changes.map((c, idx) => {
            const isLatest = idx === 0;
            return (
              <li
                key={c.changed_at}
                className="relative rounded-md border bg-background p-4 text-sm"
              >
                {/* 타임라인 노드 */}
                <span
                  aria-hidden
                  className={cn(
                    "absolute -left-[1.9rem] top-5 grid h-3 w-3 place-items-center rounded-full ring-4 ring-background",
                    isLatest ? "bg-primary" : "bg-muted-foreground/40",
                  )}
                />

                <header className="flex items-center justify-between gap-2">
                  <time className="text-xs text-muted-foreground">
                    {new Date(c.changed_at).toLocaleString("ko-KR")}
                    {isLatest ? (
                      <span className="ml-2 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                        최근
                      </span>
                    ) : null}
                  </time>
                  <Badge variant="secondary" className="font-normal">
                    {REASON_LABEL[c.reason]}
                  </Badge>
                </header>

                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground line-through">
                    {c.from_focus.length > 0
                      ? c.from_focus.join(", ")
                      : "(분류 없음)"}
                  </span>
                  <ArrowRight
                    className="h-3.5 w-3.5 text-muted-foreground"
                    aria-hidden
                  />
                  <span className="font-medium">
                    {c.to_focus.length > 0
                      ? c.to_focus.join(", ")
                      : "(분류 없음)"}
                  </span>
                </div>

                {c.notes ? (
                  <p className="mt-2 rounded bg-muted/40 px-2 py-1 text-xs text-muted-foreground">
                    {c.notes}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
    </Section>
  );
}
