import { Section } from "@/components/common/Section";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
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

// 시그널별 색 토큰 클래스 — 헤드라이너 SignalChip 과 동일한 hue.
// 진행바 배경/채움/텍스트 모두 한 hue 의 4단계로 묶여 화면 곳곳의 시그널이
// 색으로 즉시 식별된다.
const SIGNAL_BAR_STYLE: Record<keyof ConfidenceSignals, {
  track: string;
  fill: string;
  label: string;
}> = {
  self_claim: {
    track: "bg-signal-self-claim-50",
    fill: "bg-signal-self-claim-500",
    label: "text-signal-self-claim-700",
  },
  vision: {
    track: "bg-signal-vision-50",
    fill: "bg-signal-vision-500",
    label: "text-signal-vision-700",
  },
  blog: {
    track: "bg-signal-blog-50",
    fill: "bg-signal-blog-500",
    label: "text-signal-blog-700",
  },
  reviews: {
    track: "bg-signal-reviews-50",
    fill: "bg-signal-reviews-500",
    label: "text-signal-reviews-700",
  },
};

function SignalBar({
  signal,
  value,
}: {
  signal: keyof ConfidenceSignals;
  value: number;
}) {
  const pct = Math.min(100, Math.max(0, value));
  const style = SIGNAL_BAR_STYLE[signal];
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className={cn("font-medium", style.label)}>
          {SIGNAL_LABEL[signal]}
        </span>
        <span
          className="font-mono text-muted-foreground"
          title={`근거 점수 ${value} / 100`}
          aria-label={`근거 점수 ${value}`}
        >
          {value}
        </span>
      </div>
      <div className={cn("h-2 w-full overflow-hidden rounded-full", style.track)}>
        <div
          className={cn("h-full rounded-full transition-all", style.fill)}
          style={{ width: `${pct}%` }}
          aria-label={`${SIGNAL_LABEL[signal]} ${value}`}
        />
      </div>
    </div>
  );
}

// ④ 신뢰도·근거 — 데모 핵심 영역
//
// 헤드라이너 citations 배지 클릭의 스크롤 타깃이 펼침 구간에 있다.
// 펼침 구간 헤더에 시그널 색 띠를 둬 ① → ④ 시각 연결을 강화.
export function ConfidenceSection({
  confidence,
  detailed_signals,
}: ConfidenceSectionProps) {
  return (
    <Section
      id="section-confidence"
      title="분류 근거"
      badge="④"
      subtitle="이 분류가 어떤 출처의 어떤 근거로 만들어졌는지"
      action={<ConfidenceBadge confidence={confidence} />}
    >
      {/* §56 면책 — 점수는 병원 평가가 아니라 우리 분류의 근거 강도. 의료법 검수 통과 카피. */}
      <p className="mb-4 rounded-md bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
        이 점수는 병원의 진료 수준이 아니라, 우리 분류 판단의 근거가 여러 독립 출처에서
        얼마나 겹치는지를 나타냅니다. 우리는 병원을 평가하지 않고, 병원이 자기를 어떻게
        표현했고 외부 출처가 그와 얼마나 일치하는지만 보여줍니다.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {SIGNAL_KEYS.map((k) => (
          <SignalBar key={k} signal={k} value={confidence.signals[k]} />
        ))}
      </div>

      <Separator className="my-6" />

      <DetailBlock
        signal="self_claim"
        title="병원이 사이트에서 강조한 분야"
        sourceUrl={detailed_signals.self_claim.source_url}
      >
        <div className="flex flex-wrap gap-1">
          {detailed_signals.self_claim.extracted_keywords.map((k) => (
            <Badge key={k} variant="outline">
              {k}
            </Badge>
          ))}
        </div>
        <blockquote className="mt-3 rounded-md border-l-2 border-signal-self-claim-500 bg-signal-self-claim-50 px-3 py-2 text-sm text-signal-self-claim-700">
          {detailed_signals.self_claim.source_text}
        </blockquote>
      </DetailBlock>

      <Separator className="my-6" />

      <DetailBlock signal="vision" title="이미지 분포">
        {detailed_signals.vision ? (
          <>
            <ul className="space-y-1.5 text-sm">
              {Object.entries(detailed_signals.vision.image_distribution).map(
                ([key, ratio]) => (
                  <li key={key} className="flex items-center gap-3">
                    <span className="w-20 text-muted-foreground">{key}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-signal-vision-50">
                      <div
                        className="h-full rounded-full bg-signal-vision-500"
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
              <p className="mt-2 text-xs text-muted-foreground">
                감지된 장비: {detailed_signals.vision.detected_devices.join(", ")}
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            이미지 분석 없음 — Vision 은 시연 대상 병원에만 적용됩니다.
          </p>
        )}
      </DetailBlock>

      <Separator className="my-6" />

      <DetailBlock
        signal="blog"
        title={`주제 분포 (${detailed_signals.blog.total_posts}건)`}
      >
        <ul className="space-y-1.5 text-sm">
          {detailed_signals.blog.top_topics.map((t) => (
            <li key={t.topic} className="flex items-center gap-3">
              <span className="w-20 text-muted-foreground">{t.topic}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-signal-blog-50">
                <div
                  className="h-full rounded-full bg-signal-blog-500"
                  style={{ width: `${Math.round(t.frequency * 100)}%` }}
                />
              </div>
              <span className="w-10 text-right font-mono text-xs">
                {Math.round(t.frequency * 100)}%
              </span>
            </li>
          ))}
        </ul>
      </DetailBlock>

      <Separator className="my-6" />

      <DetailBlock
        signal="reviews"
        title={`키워드 (${detailed_signals.reviews.review_count}건)`}
      >
        <div className="flex flex-wrap gap-1">
          {detailed_signals.reviews.top_keywords.map((k) => (
            <Badge key={k} variant="outline">
              {k}
            </Badge>
          ))}
        </div>
      </DetailBlock>
    </Section>
  );
}

// 펼침 구간 컨테이너 — 좌측 시그널 색 띠로 ① 헤드라이너 citation 과 시각 연결
function DetailBlock({
  signal,
  title,
  sourceUrl,
  children,
}: {
  signal: keyof ConfidenceSignals;
  title: string;
  sourceUrl?: string;
  children: React.ReactNode;
}) {
  const style = SIGNAL_BAR_STYLE[signal];
  return (
    <div
      id={detailedSignalAnchorId(signal)}
      className="scroll-mt-20 border-l-2 pl-4"
      style={{ borderColor: "currentColor" }}
    >
      <div className={cn("flex items-center gap-2", style.label)}>
        <span className="text-[10px] uppercase tracking-wider">
          [{SIGNAL_LABEL[signal]}]
        </span>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-xs text-muted-foreground hover:text-foreground"
          >
            출처 ↗
          </a>
        ) : null}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}
