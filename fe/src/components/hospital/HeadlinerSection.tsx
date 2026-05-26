import { Section } from "@/components/common/Section";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { SignalChip } from "@/components/common/SignalChip";
import { HospitalThumbnail } from "@/components/common/HospitalThumbnail";
import type { AiDescription, Confidence } from "@/types/domain";

interface HeadlinerSectionProps {
  ai_description: AiDescription;
  confidence: Confidence;
  one_line_summary: string;
  /** 병원명 — 히어로 폴백 이니셜용 */
  name: string;
  /** 병원 대표 이미지 URL. null 이면 그라데이션 + 이니셜 플레이스홀더 */
  thumbnail_url: string | null;
}

// ① 헤드라이너 — 데모 핵심 영역
//
// 좌측에 큰 히어로 이미지(또는 그라데이션 폴백), 우측에 자연어 설명.
// 모바일·좁은 화면에선 이미지가 위로 쌓임.
//   - headline: 한 문장 요약. 카드 도입부 톤으로 1.2rem
//   - paragraphs: 단락별 본문 + citations 배지 묶음
//   - citations 배지는 단락 본문 끝 줄바꿈 후 한 행으로 모아 본문 흐름 유지
export function HeadlinerSection({
  ai_description,
  confidence,
  one_line_summary,
  name,
  thumbnail_url,
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
            {ai_description.headline}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">{one_line_summary}</p>
        </div>
      </div>

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
    </Section>
  );
}
