import { Link } from "react-router-dom";

import { Section } from "@/components/common/Section";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import type { RecommendationType, RelatedHospital } from "@/types/domain";

const RECO_LABEL: Record<RecommendationType, string> = {
  same_focus: "같은 주력",
  fills_gap: "빈자리 보완",
};

interface RelatedHospitalsSectionProps {
  related_hospitals: RelatedHospital[];
}

// ⑧ 관련 병원 추천
export function RelatedHospitalsSection({
  related_hospitals,
}: RelatedHospitalsSectionProps) {
  if (related_hospitals.length === 0) {
    return (
      <Section id="section-related" title="관련 병원" badge="⑧">
        <EmptyState />
      </Section>
    );
  }

  return (
    <Section
      id="section-related"
      title="관련 병원"
      badge="⑧"
      subtitle="같은 주력의 다른 병원, 또는 이 병원이 다루지 않는 분야의 대안"
    >
      <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {related_hospitals.map((r) => (
          <li
            key={r.hospital_id}
            className="rounded-md border bg-background p-3 text-sm"
          >
            <div className="flex items-center justify-between">
              <Link
                to={`/hospitals/${r.hospital_id}`}
                className="font-semibold underline-offset-2 hover:underline"
              >
                {r.name}
              </Link>
              <Badge variant="outline">{RECO_LABEL[r.recommendation_type]}</Badge>
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              {r.primary_focus.map((f) => (
                <Badge key={f} variant="secondary">
                  {f}
                </Badge>
              ))}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              유사도 {Math.round(r.similarity_score * 100)}%
              {r.distance_km != null ? ` · ${r.distance_km}km` : ""}
            </p>
          </li>
        ))}
      </ul>
    </Section>
  );
}
