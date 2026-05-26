import { Database, Clock } from "lucide-react";

import { Section } from "@/components/common/Section";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { DataMetadata, DataSource } from "@/types/domain";

const SOURCE_LABEL: Record<DataSource, string> = {
  self_site: "병원 사이트",
  public_registry: "공공등록정보",
  user_reviews: "사용자 후기",
  blog: "블로그",
};

interface MetadataSectionProps {
  metadata: DataMetadata;
}

// ⑨ 메타 정보
//
// 페이지의 "투명성 마무리" 영역. 데이터 출처와 정보 충실도가 시각적으로
// 도드라져야 사용자가 이 페이지의 정보 신뢰 기반을 한 번 더 인지한다.
export function MetadataSection({ metadata }: MetadataSectionProps) {
  const completenessPct = Math.round(metadata.data_completeness * 100);
  const completenessTone =
    completenessPct >= 80
      ? "high"
      : completenessPct >= 60
        ? "medium"
        : "low";

  return (
    <Section
      id="section-metadata"
      title="데이터 출처와 갱신"
      badge="⑨"
      subtitle="이 페이지가 어떤 자료를 언제 수집해 만들어졌는지"
    >
      {/* 정보 충실도 — 큰 게이지로 시각 마무리 */}
      <div className="rounded-md border bg-background p-4">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            정보 충실도
          </h3>
          <span
            className={cn(
              "font-mono text-base font-semibold",
              completenessTone === "high" && "text-confidence-high-700",
              completenessTone === "medium" && "text-confidence-medium-700",
              completenessTone === "low" && "text-confidence-low-700",
            )}
          >
            {completenessPct}%
          </span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full transition-all",
              completenessTone === "high" && "bg-confidence-high-500",
              completenessTone === "medium" && "bg-confidence-medium-500",
              completenessTone === "low" && "bg-confidence-low-500",
            )}
            style={{ width: `${completenessPct}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          9개 영역 중 채워진 비율 — 60% 미만이면 정보 부족 경고
        </p>
      </div>

      {/* 출처 + 갱신 시각 */}
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <MetaTile icon={<Database className="h-4 w-4" />} label="데이터 출처">
          <div className="flex flex-wrap gap-1">
            {metadata.data_sources.map((s) => (
              <Badge key={s} variant="outline" className="font-normal">
                {SOURCE_LABEL[s]}
              </Badge>
            ))}
          </div>
        </MetaTile>
        <MetaTile icon={<Clock className="h-4 w-4" />} label="마지막 갱신">
          <p className="text-sm">
            {new Date(metadata.last_updated_at).toLocaleString("ko-KR")}
          </p>
        </MetaTile>
      </div>
    </Section>
  );
}

function MetaTile({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <span aria-hidden className="text-muted-foreground">
          {icon}
        </span>
        <span>{label}</span>
      </div>
      <div className="mt-2">{children}</div>
    </div>
  );
}
