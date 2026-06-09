import { ExternalLink, Info } from "lucide-react";

import { Section } from "@/components/common/Section";
import { EmptyState } from "@/components/common/EmptyState";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Doctor } from "@/types/domain";

interface DoctorsSectionProps {
  doctors: Doctor[];
  /**
   * 심평원 신고 기준 과목별 전문의 수.
   * { "피부과": 0, "가정의학과": 1 } 형태. 빈 객체면 심평원 데이터 없음.
   */
  specialists_by_dept: Record<string, number>;
  /** 심평원 신고 기준 총 의사 수. null 이면 신고 데이터 없음 */
  total_doctors: number | null;
  /** 병원이 자기 사이트에서 표시하는 표준 진료과목 */
  standard_specialty: string;
}

// ③ 의료진 정보
//
// 인물 카드 위계:
//   - 좌측 이니셜 아바타 (사진 자리. Mock 환경엔 외부 사진 없이 이니셜만)
//   - 우측: 이름·직위 한 줄 + 자격 배지 + 세부 전공 / primary_focus + 경력
//   - 의사별 primary_focus 가 있는 경우만 강조 노출 (API 명세상 의사별 다른 케이스만 채움)
//   - source_url 이 있으면 우상단에 외부 링크 아이콘
//
// ③-보강: 의사 목록 아래에 심평원 신고 기준 전문의 수 블록 추가.
//   - specialists_by_dept 빈 객체면 전체 보강 블록 숨김 (graceful 처리).
//   - specialists_by_dept["피부과"] === 0 이고 standard_specialty 에 피부과가 포함되면
//     "진료과목으로 피부과를 표시하나 심평원 신고 기준 피부과 전문의 0명" 식 사실 노출.
//   - 단정·평가·추천 표현 금지. "심평원 신고 기준" + 수치 사실만.
export function DoctorsSection({
  doctors,
  specialists_by_dept,
  total_doctors,
  standard_specialty,
}: DoctorsSectionProps) {
  const hasDeptData = Object.keys(specialists_by_dept).length > 0;

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

      {/* 심평원 신고 기준 전문의 수 보강 블록 — 데이터 있을 때만 렌더 */}
      {hasDeptData && (
        <HiraSpecialistBlock
          specialists_by_dept={specialists_by_dept}
          total_doctors={total_doctors}
          standard_specialty={standard_specialty}
        />
      )}
    </Section>
  );
}

// 심평원 신고 기준 전문의 수 블록
// 출처 명시: "병원이 심평원에 신고한 기준" — 주체 = 병원, 근거 = 심평원 신고.
function HiraSpecialistBlock({
  specialists_by_dept,
  total_doctors,
  standard_specialty,
}: {
  specialists_by_dept: Record<string, number>;
  total_doctors: number | null;
  standard_specialty: string;
}) {
  const entries = Object.entries(specialists_by_dept);

  return (
    <div className="mt-4 rounded-md border border-blue-200 bg-blue-50/60 p-3">
      <div className="mb-2 flex items-center gap-1.5">
        <Info className="h-3.5 w-3.5 shrink-0 text-blue-600" aria-hidden />
        <span className="text-xs font-semibold text-blue-700">
          심평원 신고 기준 의사 현황
        </span>
        <Badge
          variant="outline"
          className="ml-auto border-blue-300 bg-white text-blue-700 text-[10px] px-1.5 py-0"
        >
          심평원 신고
        </Badge>
      </div>

      {total_doctors !== null && (
        <p className="mb-2 text-xs text-blue-800">
          병원이 심평원에 신고한 총 의사 수:{" "}
          <span className="font-semibold">{total_doctors}명</span>
        </p>
      )}

      <ul className="space-y-1">
        {entries.map(([dept, count]) => {
          // 간판-진실성 대조: 병원이 standard_specialty 로 해당 과를 표시하나 심평원 신고 전문의 0명인 경우
          const isSignboardMismatch =
            count === 0 &&
            standard_specialty.length > 0 &&
            (standard_specialty === dept ||
              standard_specialty.includes(dept) ||
              dept.includes(standard_specialty));

          return (
            <li key={dept} className="flex flex-wrap items-center gap-1.5 text-xs">
              {isSignboardMismatch ? (
                // 간판-진실성 불일치: 사실 노출 (대조 톤 배제 — 순차 서술로 중립화)
                <span className="text-amber-700">
                  진료과목으로{" "}
                  <span className="font-semibold">{dept}</span> 표시됨.
                  심평원 신고 기준 해당 과 전문의{" "}
                  <span className="font-semibold">0명</span>
                </span>
              ) : (
                // 일반 전문의 수 표시
                <span className="text-blue-800">
                  심평원 신고 기준{" "}
                  <span className="font-semibold">{dept}</span> 전문의{" "}
                  <span className="font-semibold">{count}명</span>
                </span>
              )}
            </li>
          );
        })}
      </ul>

      <p className="mt-2 text-[10px] leading-relaxed text-blue-600/70">
        병원이 심평원에 신고한 수치를 그대로 표시합니다. 실제 진료 여부와 다를 수 있으므로 병원에 직접 확인하세요.
      </p>
    </div>
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
