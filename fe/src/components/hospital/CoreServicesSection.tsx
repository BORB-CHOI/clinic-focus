import { Link } from "react-router-dom";

import { Section } from "@/components/common/Section";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type {
  Equipment,
  ExcludedReason,
  ExcludedService,
  PriceItem,
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
}

// ② 핵심 진료 정보
export function CoreServicesSection({
  standard_specialty,
  primary_focus,
  services,
  excluded_services,
  equipment,
  prices,
}: CoreServicesSectionProps) {
  const grouped = services.reduce<Record<ServiceCategory, Service[]>>(
    (acc, s) => {
      acc[s.category] = acc[s.category] ?? [];
      acc[s.category].push(s);
      return acc;
    },
    {} as Record<ServiceCategory, Service[]>,
  );

  return (
    <Section
      id="section-core-services"
      title="진료 정보"
      badge="②"
      subtitle="이 병원이 사이트·후기·이미지에서 어떤 진료를 메인으로 표시하는지"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{standard_specialty}</Badge>
        {primary_focus.map((f) => (
          <Badge key={f}>{f}</Badge>
        ))}
      </div>

      <div className="mt-6 space-y-4">
        {(Object.keys(grouped) as ServiceCategory[]).map((cat) => (
          <div key={cat}>
            <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
              {CATEGORY_LABEL[cat]}
            </h3>
            <div className="flex flex-wrap gap-2">
              {grouped[cat].map((s) => (
                <Badge key={s.name} variant="outline">
                  {s.name}
                </Badge>
              ))}
            </div>
          </div>
        ))}
      </div>

      <Separator className="my-6" />

      <div>
        <h3 className="mb-2 text-sm font-semibold">보유 의료기기</h3>
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {equipment.map((e) => (
            <li
              key={e.name}
              className="flex items-center justify-between rounded-md border bg-background px-3 py-2 text-sm"
            >
              <span className={e.available ? "" : "text-muted-foreground line-through"}>
                {e.name}
              </span>
              <span className="text-xs text-muted-foreground">
                {e.available ? "보유" : "미보유"}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {prices.length > 0 ? (
        <>
          <Separator className="my-6" />
          <div>
            <h3 className="mb-2 text-sm font-semibold">비급여 가격</h3>
            <ul className="space-y-1 text-sm">
              {prices.map((p) => (
                <li
                  key={p.service_name}
                  className="flex items-center justify-between"
                >
                  <span>{p.service_name}</span>
                  <span className="font-mono text-muted-foreground">
                    {p.price_range}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}

      {excluded_services.length > 0 ? (
        <>
          <Separator className="my-6" />
          <div>
            <h3 className="mb-2 text-sm font-semibold">다루지 않는 분야</h3>
            <ul className="space-y-2 text-sm">
              {excluded_services.map((ex) => (
                <li key={ex.name} className="rounded-md border bg-muted/40 p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{ex.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {EXCLUDED_REASON_LABEL[ex.reason]}
                    </span>
                  </div>
                  {ex.alternative_hospital_ids.length > 0 ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      동네 대안:{" "}
                      {ex.alternative_hospital_ids.map((id, i) => (
                        <span key={id}>
                          <Link
                            to={`/hospitals/${id}`}
                            className="underline-offset-2 hover:underline"
                          >
                            {id}
                          </Link>
                          {i < ex.alternative_hospital_ids.length - 1
                            ? ", "
                            : null}
                        </span>
                      ))}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}
    </Section>
  );
}
