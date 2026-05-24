import { Link } from "react-router-dom";
import { Check, X, ArrowRight } from "lucide-react";

import { Section } from "@/components/common/Section";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type {
  Equipment,
  ExcludedReason,
  ExcludedService,
  PriceItem,
  RelatedHospital,
  Service,
  ServiceCategory,
} from "@/types/domain";

const CATEGORY_LABEL: Record<ServiceCategory, string> = {
  general: "일반 진료",
  cosmetic: "미용 시술",
  surgery: "수술",
  exam: "검사",
  other: "기타",
};

const EXCLUDED_REASON_LABEL: Record<ExcludedReason, string> = {
  no_equipment: "장비 없음",
  no_mention: "사이트 언급 없음",
  low_signal: "신호 부족",
};

interface CoreServicesSectionProps {
  standard_specialty: string;
  primary_focus: string[];
  services: Service[];
  excluded_services: ExcludedService[];
  equipment: Equipment[];
  prices: PriceItem[];
  /** 대안 병원 ID 를 이름으로 풀어주기 위한 동일 페이지의 추천 목록 */
  related_hospitals: RelatedHospital[];
}

// ② 핵심 진료 정보 — 4 서브섹션 위계 + 헛걸음 방지 카드
//
// 위계:
//   1) 분류 태그 (표준 진료과목 + 주력 분야)         — 한 줄 요약
//   2) 다루는 진료 항목 (카테고리별 그룹)              — 일반/미용/수술/검사
//   3) 보유 의료기기 (○/✗)                            — 시술 결정 근거
//   4) 비급여 가격 (있을 때만)                         — 사전 정보
//   5) 다루지 않는 분야 + 대안 병원 (헛걸음 방지)      — 본 서비스 핵심 카피
//
// 5)의 alternative_hospital_ids 는 related_hospitals 에서 이름을 매핑.
// 매핑이 안 되면 ID 그대로 노출 (BE 응답 누락 폴백).
export function CoreServicesSection({
  standard_specialty,
  primary_focus,
  services,
  excluded_services,
  equipment,
  prices,
  related_hospitals,
}: CoreServicesSectionProps) {
  // 카테고리별 그룹화 (등록 순서 유지)
  const grouped = services.reduce<Record<ServiceCategory, Service[]>>(
    (acc, s) => {
      acc[s.category] = acc[s.category] ?? [];
      acc[s.category].push(s);
      return acc;
    },
    {} as Record<ServiceCategory, Service[]>,
  );

  // 보유 / 미보유 분리. 미보유는 헛걸음 방지 정보라 별도 노출
  const equipmentAvailable = equipment.filter((e) => e.available);
  const equipmentMissing = equipment.filter((e) => !e.available);

  // 대안 병원 이름 매핑
  const altById = new Map(related_hospitals.map((h) => [h.hospital_id, h]));

  return (
    <Section
      id="section-core-services"
      title="진료 정보"
      badge="②"
      subtitle="이 병원이 사이트·후기·이미지에서 어떤 진료를 메인으로 표시하는지"
    >
      {/* 1) 분류 태그 */}
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{standard_specialty}</Badge>
        {primary_focus.map((f) => (
          <Badge key={f}>{f}</Badge>
        ))}
      </div>

      <Separator className="my-6" />

      {/* 2) 다루는 진료 항목 */}
      <SubHeading>다루는 진료 항목</SubHeading>
      <div className="space-y-4">
        {(Object.keys(grouped) as ServiceCategory[]).map((cat) => (
          <div key={cat}>
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {CATEGORY_LABEL[cat]}
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {grouped[cat].map((s) => (
                <Badge key={s.name} variant="secondary" className="font-normal">
                  {s.name}
                </Badge>
              ))}
            </div>
          </div>
        ))}
      </div>

      <Separator className="my-6" />

      {/* 3) 보유 의료기기 — 보유/미보유 분리해서 의미 명시 */}
      <SubHeading>보유 의료기기</SubHeading>
      <div className="grid gap-2 sm:grid-cols-2">
        {equipmentAvailable.map((e) => (
          <EquipmentItem key={e.name} equipment={e} />
        ))}
      </div>
      {equipmentMissing.length > 0 ? (
        <div className="mt-4">
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            미보유 (확인됨)
          </h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {equipmentMissing.map((e) => (
              <EquipmentItem key={e.name} equipment={e} />
            ))}
          </div>
        </div>
      ) : null}

      {/* 4) 비급여 가격 — 있을 때만 */}
      {prices.length > 0 ? (
        <>
          <Separator className="my-6" />
          <SubHeading>비급여 가격</SubHeading>
          <ul className="divide-y rounded-md border bg-background">
            {prices.map((p) => (
              <li
                key={p.service_name}
                className="flex items-center justify-between px-3 py-2 text-sm"
              >
                <span>{p.service_name}</span>
                <span className="font-mono text-muted-foreground">
                  {p.price_range}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {/* 5) 다루지 않는 분야 — 헛걸음 방지 */}
      {excluded_services.length > 0 ? (
        <>
          <Separator className="my-6" />
          <SubHeading>다루지 않는 분야</SubHeading>
          <p className="-mt-2 mb-3 text-xs text-muted-foreground">
            이 병원이 메인으로 표시하지 않거나 장비가 없는 진료입니다.
          </p>
          <ul className="space-y-2">
            {excluded_services.map((ex) => (
              <ExcludedItem
                key={ex.name}
                excluded={ex}
                altById={altById}
              />
            ))}
          </ul>
        </>
      ) : null}
    </Section>
  );
}

function SubHeading({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-3 text-sm font-semibold">{children}</h3>;
}

function EquipmentItem({ equipment }: { equipment: Equipment }) {
  const Icon = equipment.available ? Check : X;
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-2 rounded-md border bg-background px-3 py-2 text-sm",
        equipment.available
          ? "border-confidence-high-100"
          : "border-dashed",
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span
          className={cn(
            "grid h-5 w-5 shrink-0 place-items-center rounded-full",
            equipment.available
              ? "bg-confidence-high-50 text-confidence-high-700"
              : "bg-muted text-muted-foreground",
          )}
          aria-hidden
        >
          <Icon className="h-3 w-3" strokeWidth={3} />
        </span>
        <span
          className={cn(
            "truncate",
            !equipment.available && "text-muted-foreground",
          )}
        >
          {equipment.name}
        </span>
      </div>
    </div>
  );
}

function ExcludedItem({
  excluded,
  altById,
}: {
  excluded: ExcludedService;
  altById: Map<string, RelatedHospital>;
}) {
  return (
    <li className="rounded-md border border-dashed bg-muted/30 p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{excluded.name}</span>
        <span className="text-xs text-muted-foreground">
          {EXCLUDED_REASON_LABEL[excluded.reason]}
        </span>
      </div>
      {excluded.alternative_hospital_ids.length > 0 ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted-foreground">동네 대안:</span>
          {excluded.alternative_hospital_ids.map((id) => {
            const hospital = altById.get(id);
            return (
              <Link
                key={id}
                to={`/hospitals/${id}`}
                className="inline-flex items-center gap-1 rounded-full border border-input bg-background px-2 py-0.5 transition-colors hover:border-primary/40 hover:bg-accent hover:text-accent-foreground"
              >
                {hospital?.name ?? id}
                <ArrowRight className="h-3 w-3" aria-hidden />
              </Link>
            );
          })}
        </div>
      ) : null}
    </li>
  );
}
