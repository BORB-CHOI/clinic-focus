import { ExternalLink } from "lucide-react";

import { Section } from "@/components/common/Section";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Doctor } from "@/types/domain";

interface DoctorsSectionProps {
  doctors: Doctor[];
}

// ③ 의료진 정보
//
// 인물 카드 위계:
//   - 좌측 이니셜 아바타 (사진 자리. Mock 환경엔 외부 사진 없이 이니셜만)
//   - 우측: 이름·직위 한 줄 + 자격 배지 + 세부 전공 / primary_focus + 경력
//   - 의사별 primary_focus 가 있는 경우만 강조 노출 (API 명세상 의사별 다른 케이스만 채움)
//   - source_url 이 있으면 우상단에 외부 링크 아이콘
export function DoctorsSection({ doctors }: DoctorsSectionProps) {
  return (
    <Section
      id="section-doctors"
      title="의료진"
      badge="③"
      subtitle="원장·진료의별 자격·세부 전공"
    >
      {doctors.length === 0 ? (
        <EmptyState />
      ) : (
        <ul className="space-y-3">
          {doctors.map((d, idx) => (
            <li key={`${d.name}-${idx}`}>
              <DoctorCard doctor={d} />
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function DoctorCard({ doctor }: { doctor: Doctor }) {
  const initial = doctor.name.charAt(0);
  const hasPrimaryFocus =
    doctor.primary_focus !== null && doctor.primary_focus.length > 0;

  return (
    <article className="flex gap-4 rounded-md border bg-background p-4">
      <Avatar initial={initial} />

      <div className="min-w-0 flex-1">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="text-base font-semibold tracking-tight">
              {doctor.name}
            </span>
            <span className="text-sm text-muted-foreground">
              {doctor.position}
            </span>
          </div>
          {doctor.source_url ? (
            <a
              href={doctor.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden />
              <span>출처</span>
            </a>
          ) : null}
        </header>

        {/* 자격 + 세부 전공 한 줄 */}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {doctor.specialty_certifications.map((c) => (
            <Badge key={c} variant="secondary" className="font-normal">
              {c}
            </Badge>
          ))}
          {doctor.sub_specialty ? (
            <span className="text-xs text-muted-foreground">
              · 세부 전공{" "}
              <span className="font-medium text-foreground">
                {doctor.sub_specialty}
              </span>
            </span>
          ) : null}
        </div>

        {/* 의사별 primary_focus — 다른 의사와 진료 분야가 다를 때만 */}
        {hasPrimaryFocus ? (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">
              이 의사 진료 분야:
            </span>
            {doctor.primary_focus!.map((f) => (
              <Badge key={f} className="font-normal">
                {f}
              </Badge>
            ))}
          </div>
        ) : null}

        {doctor.career.length > 0 ? (
          <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
            {doctor.career.map((line) => (
              <li key={line} className="flex gap-2">
                <span aria-hidden className="mt-1 h-1 w-1 shrink-0 rounded-full bg-muted-foreground/60" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </article>
  );
}

function Avatar({ initial, className }: { initial: string; className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "grid h-12 w-12 shrink-0 place-items-center rounded-full bg-secondary text-base font-semibold text-secondary-foreground",
        className,
      )}
    >
      {initial}
    </div>
  );
}
