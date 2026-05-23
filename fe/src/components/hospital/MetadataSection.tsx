import { Section } from "@/components/common/Section";
import { Badge } from "@/components/ui/badge";
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
export function MetadataSection({ metadata }: MetadataSectionProps) {
  const completenessPct = Math.round(metadata.data_completeness * 100);
  return (
    <Section
      id="section-metadata"
      title="데이터 출처와 갱신"
      badge="⑨"
      subtitle="평가 투명성을 위한 메타 정보"
    >
      <ul className="space-y-2 text-sm">
        <li className="flex justify-between">
          <span className="text-muted-foreground">마지막 갱신</span>
          <span>
            {new Date(metadata.last_updated_at).toLocaleString("ko-KR")}
          </span>
        </li>
        <li className="flex items-start justify-between gap-4">
          <span className="text-muted-foreground">데이터 출처</span>
          <span className="flex flex-wrap justify-end gap-1">
            {metadata.data_sources.map((s) => (
              <Badge key={s} variant="outline">
                {SOURCE_LABEL[s]}
              </Badge>
            ))}
          </span>
        </li>
        <li className="flex items-center justify-between">
          <span className="text-muted-foreground">정보 충실도</span>
          <span className="flex items-center gap-2">
            <span className="h-2 w-24 overflow-hidden rounded-full bg-muted">
              <span
                className="block h-full bg-primary"
                style={{ width: `${completenessPct}%` }}
              />
            </span>
            <span className="font-mono text-xs">{completenessPct}%</span>
          </span>
        </li>
      </ul>
    </Section>
  );
}
