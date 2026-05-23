import { Section } from "@/components/common/Section";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
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
            className="text-sm text-primary underline-offset-2 hover:underline"
          >
            전체 이력
          </a>
        ) : null
      }
    >
      {recent_changes.length === 0 ? (
        <EmptyState message="변경 이력 없음" />
      ) : (
        <ol className="space-y-3">
          {recent_changes.map((c) => (
            <li
              key={c.changed_at}
              className="rounded-md border bg-background p-3 text-sm"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">
                  {new Date(c.changed_at).toLocaleString("ko-KR")}
                </span>
                <Badge variant="secondary">{REASON_LABEL[c.reason]}</Badge>
              </div>
              <p className="mt-2">
                <span className="text-muted-foreground line-through">
                  {c.from_focus.join(", ") || "(없음)"}
                </span>
                <span className="mx-2">→</span>
                <span className="font-medium">
                  {c.to_focus.join(", ") || "(없음)"}
                </span>
              </p>
              {c.notes ? (
                <p className="mt-1 text-xs text-muted-foreground">{c.notes}</p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}
