import { Link } from "react-router-dom";
import { ArrowRight, MapPin } from "lucide-react";

import { Section } from "@/components/common/Section";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { RecommendationType, RelatedHospital } from "@/types/domain";

interface RelatedHospitalsSectionProps {
  related_hospitals: RelatedHospital[];
}

// ⑧ 관련 병원 추천
//
// recommendation_type 으로 그룹화 — "같은 주력" / "빈자리 보완" 두 의미가
// 명확히 다르므로 한 그리드에 섞어 놓으면 사용자가 의도를 인지하기 어렵다.
//   같은 주력  : 이 병원과 비슷한 진료 톤 (대안 후보)
//   빈자리 보완: 이 병원이 안 다루는 분야의 동네 대안
export function RelatedHospitalsSection({
  related_hospitals,
}: RelatedHospitalsSectionProps) {
  if (related_hospitals.length === 0) {
    return (
      <Section
        id="section-related"
        title="관련 병원"
        badge="⑧"
        subtitle="같은 주력의 다른 병원, 또는 이 병원이 다루지 않는 분야의 대안"
      >
        <EmptyState />
      </Section>
    );
  }

  const sameFocus = related_hospitals.filter(
    (r) => r.recommendation_type === "same_focus",
  );
  const fillsGap = related_hospitals.filter(
    (r) => r.recommendation_type === "fills_gap",
  );

  return (
    <Section
      id="section-related"
      title="관련 병원"
      badge="⑧"
      subtitle="같은 주력의 다른 병원, 또는 이 병원이 다루지 않는 분야의 대안"
    >
      <div className="space-y-5">
        {sameFocus.length > 0 ? (
          <RecoGroup
            label="같은 주력"
            description="비슷한 진료 톤의 동네 다른 병원"
            type="same_focus"
            items={sameFocus}
          />
        ) : null}
        {fillsGap.length > 0 ? (
          <RecoGroup
            label="빈자리 보완"
            description="이 병원이 안 다루는 분야의 동네 대안"
            type="fills_gap"
            items={fillsGap}
          />
        ) : null}
      </div>
    </Section>
  );
}

function RecoGroup({
  label,
  description,
  type,
  items,
}: {
  label: string;
  description: string;
  type: RecommendationType;
  items: RelatedHospital[];
}) {
  return (
    <div>
      <header className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{label}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </header>
      <ul className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {items.map((r) => (
          <li key={r.hospital_id}>
            <RelatedCard hospital={r} type={type} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function RelatedCard({
  hospital,
  type,
}: {
  hospital: RelatedHospital;
  type: RecommendationType;
}) {
  const sim = Math.round(hospital.similarity_score * 100);
  return (
    <Link
      to={`/hospitals/${hospital.hospital_id}`}
      className={cn(
        "group block rounded-md border bg-background p-3 text-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm",
        type === "fills_gap" && "border-dashed",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-semibold">{hospital.name}</span>
        <ArrowRight
          className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary"
          aria-hidden
        />
      </div>

      <div className="mt-1.5 flex flex-wrap gap-1">
        {hospital.primary_focus.map((f) => (
          <Badge key={f} variant="secondary" className="font-normal">
            {f}
          </Badge>
        ))}
      </div>

      <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-mono">유사도 {sim}%</span>
        {hospital.distance_km != null ? (
          <>
            <span aria-hidden>·</span>
            <span className="inline-flex items-center gap-0.5">
              <MapPin className="h-3 w-3" aria-hidden />
              {hospital.distance_km.toFixed(1)}km
            </span>
          </>
        ) : null}
      </p>
    </Link>
  );
}
