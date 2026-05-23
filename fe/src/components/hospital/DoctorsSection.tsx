import { Section } from "@/components/common/Section";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import type { Doctor } from "@/types/domain";

interface DoctorsSectionProps {
  doctors: Doctor[];
}

// ③ 의료진 정보
export function DoctorsSection({ doctors }: DoctorsSectionProps) {
  return (
    <Section id="section-doctors" title="의료진" badge="③">
      {doctors.length === 0 ? (
        <EmptyState />
      ) : (
        <ul className="space-y-4">
          {doctors.map((d, idx) => (
            <li
              key={`${d.name}-${idx}`}
              className="rounded-md border bg-background p-4"
            >
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-base font-semibold">{d.name}</span>
                <span className="text-sm text-muted-foreground">
                  {d.position}
                </span>
              </div>

              {d.specialty_certifications.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {d.specialty_certifications.map((c) => (
                    <Badge key={c} variant="secondary">
                      {c}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {d.sub_specialty ? (
                <p className="mt-2 text-sm">
                  세부 전공: <span className="font-medium">{d.sub_specialty}</span>
                </p>
              ) : null}

              {d.career.length > 0 ? (
                <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
                  {d.career.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
