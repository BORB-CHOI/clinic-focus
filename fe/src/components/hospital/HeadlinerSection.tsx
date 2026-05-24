import { Section } from "@/components/common/Section";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { SignalChip } from "@/components/common/SignalChip";
import type { AiDescription, Confidence } from "@/types/domain";

interface HeadlinerSectionProps {
  ai_description: AiDescription;
  confidence: Confidence;
  one_line_summary: string;
}

// ① 헤드라이너 — 데모 핵심 영역
//
// AI 통합 자연어 설명(ai_description)이 본 서비스의 차별점이라 이 영역의
// 정보 위계 + 출처 시그널 가시성이 가장 중요하다.
//   - headline: 한 문장 요약. 카드 도입부 톤으로 1.2rem (라운드 5에서 정돈)
//   - paragraphs: 단락별 본문 + citations 배지 묶음
//   - citations 배지는 단락 본문 끝 줄바꿈 후 한 행으로 모아 본문 흐름 유지
export function HeadlinerSection({
  ai_description,
  confidence,
  one_line_summary,
}: HeadlinerSectionProps) {
  return (
    <Section
      id="section-headliner"
      title="요약"
      badge="①"
      action={<ConfidenceBadge confidence={confidence} />}
    >
      <p className="text-[1.2rem] font-semibold leading-snug tracking-tight">
        {ai_description.headline}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">{one_line_summary}</p>

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
