import { Section } from "@/components/common/Section";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { SignalChip } from "@/components/common/SignalChip";
import { HospitalThumbnail } from "@/components/common/HospitalThumbnail";
import type { AiDescription, Confidence } from "@/types/domain";

interface HeadlinerSectionProps {
  /** 비-시연 병원은 null — AI 단락 대신 요약·안내로 차등 렌더 */
  ai_description: AiDescription | null;
  confidence: Confidence;
  one_line_summary: string;
  /** 병원명 — 히어로 폴백 이니셜용 */
  name: string;
  /** 병원 대표 이미지 URL. null 이면 그라데이션 + 이니셜 플레이스홀더 */
  thumbnail_url: string | null;
  /**
   * 표준 진료과목. ai_description null 시 fallback 카드 모드에서 크게 표시.
   * 빈 문자열이면 미분류 병원
   */
  standard_specialty: string;
  /**
   * 룰 기반 주력 태그 배열. ai_description null 시 fallback 카드 모드에서 칩으로 표시.
   * 빈 배열이면 아직 분류 전
   */
  primary_focus: string[];
}

// ① 헤드라이너 — 데모 핵심 영역
//
// 좌측에 큰 히어로 이미지(또는 그라데이션 폴백), 우측에 자연어 설명.
// 모바일·좁은 화면에선 이미지가 위로 쌓임.
//   - headline: 한 문장 요약. 카드 도입부 톤으로 1.2rem
//   - paragraphs: 단락별 본문 + citations 배지 묶음
//   - citations 배지는 단락 본문 끝 줄바꿈 후 한 행으로 모아 본문 흐름 유지
//
// ai_description === null (비-시연 병원):
//   표준과목 + 주력태그 fallback 카드 모드로 렌더. 빈 안내 텍스트만 나오는 대신
//   이미 수집된 분류 결과(standard_specialty·primary_focus·confidence)를
//   의미있게 보여주어 서비스 핵심 차별점을 데모 500개 외에도 전달.
export function HeadlinerSection({
  ai_description,
  confidence,
  one_line_summary,
  name,
  thumbnail_url,
  standard_specialty,
  primary_focus,
}: HeadlinerSectionProps) {
  return (
    <Section
      id="section-headliner"
      title="요약"
      badge="①"
      action={<ConfidenceBadge confidence={confidence} />}
    >
      <div className="flex flex-col gap-4 sm:flex-row">
        {/* 히어로 이미지 자리 — BE 이미지 미구현 단계엔 그라데이션 폴백 */}
        <HospitalThumbnail
          src={thumbnail_url}
          name={name}
          className="h-40 w-full sm:h-32 sm:w-32"
        />

        <div className="min-w-0 flex-1">
          <p className="text-[1.2rem] font-semibold leading-snug tracking-tight">
            {ai_description?.headline || one_line_summary || `${name} 분류 요약`}
          </p>
          {ai_description && one_line_summary ? (
            <p className="mt-2 text-sm text-muted-foreground">{one_line_summary}</p>
          ) : null}
        </div>
      </div>

      {ai_description ? (
        <>
          <div className="mt-6 space-y-5">
            {ai_description.paragraphs.map((p, idx) => (
              <div key={idx} className="space-y-2">
                <p className="text-[15px] leading-relaxed">{p.text}</p>
                <div className="flex flex-wrap items-center gap-1">
                  <span className="mr-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                    출처
                  </span>
                  {p.citations.map((c) => (
                    <SignalChip key={c} signal={c} />
                  ))}
                </div>
              </div>
            ))}
          </div>

          <p className="mt-6 text-xs text-muted-foreground">
            AI 생성 · {new Date(ai_description.generated_at).toLocaleString("ko-KR")}
          </p>
        </>
      ) : (
        /* ai_description null — fallback 카드 모드
           이미 수집된 분류 결과(표준과목·주력태그·confidence)를 카드로 표시.
           우리 서비스 핵심 차별점("표준 카테고리 너머 실제 주력")을 빈 화면 대신 보여줌. */
        <div className="mt-4 space-y-4">
          {/* 표준 진료과목 — 크게 */}
          <div className="flex flex-col gap-1">
            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              표준 진료과목
            </span>
            {standard_specialty ? (
              <span className="text-2xl font-bold tracking-tight">
                {standard_specialty}
              </span>
            ) : (
              <span className="text-sm text-muted-foreground">
                분류 전 — 표준과목 미확인
              </span>
            )}
          </div>

          {/* 주력 태그 — 서비스 핵심 차별점 */}
          {primary_focus.length > 0 ? (
            <div className="flex flex-col gap-2">
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {/* 카피: "이 병원이 자기 사이트에서 주력으로 표시한 분야" 의미로 작성 */}
                이 병원이 자기 사이트에서 주력으로 표시한 분야
              </span>
              <div className="flex flex-wrap gap-2">
                {primary_focus.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-sm font-medium text-primary"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                주력 분야
              </span>
              <span className="text-sm text-muted-foreground">
                분류 전 — 주력 태그 미확인
              </span>
            </div>
          )}

          {/* 안내 문구 — 보조 역할, 주체 명시 원칙 준수 */}
          <p className="rounded-md bg-muted/40 px-3 py-2 text-[12px] leading-relaxed text-muted-foreground">
            AI 통합 설명은 시연 약 500개 병원에만 생성됩니다. 위 분류는 이
            병원 공식 사이트에서 자동 수집한 정보를 기반으로 합니다.
            아래 <span className="font-medium text-foreground">진료 정보</span>{" "}
            탭에서 근거 시그널(병원 사이트·후기·블로그)을 확인하세요.
          </p>
        </div>
      )}
    </Section>
  );
}
