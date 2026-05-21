import { Section } from "@/components/common/Section";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { SIGNAL_LABEL, detailedSignalAnchorId } from "@/lib/signals";
import type {
  Confidence,
  ConfidenceSignals,
  DetailedSignals,
} from "@/types/domain";

interface ConfidenceSectionProps {
  confidence: Confidence;
  detailed_signals: DetailedSignals;
}

const SIGNAL_KEYS: (keyof ConfidenceSignals)[] = [
  "self_claim",
  "vision",
  "blog",
  "reviews",
];

function SignalBar({ label, value }: { label: string; value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono">{value}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary"
          style={{ width: `${pct}%` }}
          aria-label={`${label} ${value}`}
        />
      </div>
    </div>
  );
}

// ④ 신뢰도·근거 — 데모 핵심 영역
// 헤드라이너 citations 배지 클릭의 스크롤 타깃
export function ConfidenceSection({
  confidence,
  detailed_signals,
}: ConfidenceSectionProps) {
  return (
    <Section
      id="section-confidence"
      title="신뢰도와 근거"
      badge="④"
      subtitle="이 분류가 어떤 시그널의 어떤 근거로 만들어졌는지"
      action={<ConfidenceBadge confidence={confidence} />}
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {SIGNAL_KEYS.map((k) => (
          <SignalBar
            key={k}
            label={SIGNAL_LABEL[k]}
            value={confidence.signals[k]}
          />
        ))}
      </div>

      <Separator className="my-6" />

      <div
        id={detailedSignalAnchorId("self_claim")}
        className="scroll-mt-20 space-y-2"
      >
        <h3 className="text-sm font-semibold">[사이트] 자칭 컨셉</h3>
        <div className="flex flex-wrap gap-1">
          {detailed_signals.self_claim.extracted_keywords.map((k) => (
            <Badge key={k} variant="outline">
              {k}
            </Badge>
          ))}
        </div>
        <blockquote className="rounded-md border-l-2 bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          {detailed_signals.self_claim.source_text}
        </blockquote>
      </div>

      <Separator className="my-6" />

      <div
        id={detailedSignalAnchorId("vision")}
        className="scroll-mt-20 space-y-2"
      >
        <h3 className="text-sm font-semibold">[Vision] 이미지 분포</h3>
        <ul className="space-y-1 text-sm">
          {Object.entries(detailed_signals.vision.image_distribution).map(
            ([key, ratio]) => (
              <li key={key} className="flex items-center gap-3">
                <span className="w-20 text-muted-foreground">{key}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full bg-primary/70"
                    style={{ width: `${Math.round(ratio * 100)}%` }}
                  />
                </div>
                <span className="w-10 text-right font-mono text-xs">
                  {Math.round(ratio * 100)}%
                </span>
              </li>
            ),
          )}
        </ul>
        {detailed_signals.vision.detected_devices.length > 0 ? (
          <p className="text-xs text-muted-foreground">
            감지된 장비: {detailed_signals.vision.detected_devices.join(", ")}
          </p>
        ) : null}
      </div>

      <Separator className="my-6" />

      <div
        id={detailedSignalAnchorId("blog")}
        className="scroll-mt-20 space-y-2"
      >
        <h3 className="text-sm font-semibold">
          [블로그] 주제 분포 ({detailed_signals.blog.total_posts}건)
        </h3>
        <ul className="space-y-1 text-sm">
          {detailed_signals.blog.top_topics.map((t) => (
            <li key={t.topic} className="flex items-center gap-3">
              <span className="w-20 text-muted-foreground">{t.topic}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary/70"
                  style={{ width: `${Math.round(t.frequency * 100)}%` }}
                />
              </div>
              <span className="w-10 text-right font-mono text-xs">
                {Math.round(t.frequency * 100)}%
              </span>
            </li>
          ))}
        </ul>
      </div>

      <Separator className="my-6" />

      <div
        id={detailedSignalAnchorId("reviews")}
        className="scroll-mt-20 space-y-2"
      >
        <h3 className="text-sm font-semibold">
          [후기] 키워드 ({detailed_signals.reviews.review_count}건)
        </h3>
        <div className="flex flex-wrap gap-1">
          {detailed_signals.reviews.top_keywords.map((k) => (
            <Badge key={k} variant="outline">
              {k}
            </Badge>
          ))}
        </div>
      </div>
    </Section>
  );
}
