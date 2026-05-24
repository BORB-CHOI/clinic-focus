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
// headline 큰 글씨 + 단락별 citations 배지
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
      <p className="text-[1.2rem] font-semibold leading-snug">
        {ai_description.headline}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">{one_line_summary}</p>

      <div className="mt-6 space-y-4">
        {ai_description.paragraphs.map((p, idx) => (
          <p key={idx} className="text-[15px] leading-relaxed">
            {p.text}
            <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
              {p.citations.map((c) => (
                <SignalChip key={c} signal={c} />
              ))}
            </span>
          </p>
        ))}
      </div>

      <p className="mt-6 text-xs text-muted-foreground">
        AI 생성 · {new Date(ai_description.generated_at).toLocaleString("ko-KR")}
      </p>
    </Section>
  );
}
