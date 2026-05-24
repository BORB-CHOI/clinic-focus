import { cn } from "@/lib/utils";
import { SIGNAL_LABEL, detailedSignalAnchorId } from "@/lib/signals";
import type { SignalKey } from "@/types/domain";

interface SignalChipProps {
  signal: SignalKey;
  className?: string;
}

// 시그널 키 → 색 토큰. 4 시그널이 한 화면(헤드라이너 단락 끝)에 동시에
// 등장해도 색 거리가 멀어 구분이 즉시 됨. tailwind.config.js 의 signal.* 매핑.
const SIGNAL_STYLE: Record<Exclude<SignalKey, "public_data">, string> = {
  self_claim:
    "bg-signal-self-claim-50 text-signal-self-claim-700 border-signal-self-claim-100 hover:bg-signal-self-claim-100",
  vision:
    "bg-signal-vision-50 text-signal-vision-700 border-signal-vision-100 hover:bg-signal-vision-100",
  blog:
    "bg-signal-blog-50 text-signal-blog-700 border-signal-blog-100 hover:bg-signal-blog-100",
  reviews:
    "bg-signal-reviews-50 text-signal-reviews-700 border-signal-reviews-100 hover:bg-signal-reviews-100",
};

// citations 배지 — 클릭 시 상세 페이지 ④ detailed_signals 해당 섹션으로 스크롤
// public_data는 detailed_signals에 없으므로 클릭 비활성 + 중립 톤
export function SignalChip({ signal, className }: SignalChipProps) {
  const label = SIGNAL_LABEL[signal];

  if (signal === "public_data") {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded border bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground",
          className,
        )}
      >
        [{label}]
      </span>
    );
  }

  return (
    <a
      href={`#${detailedSignalAnchorId(signal)}`}
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium transition-colors",
        SIGNAL_STYLE[signal],
        className,
      )}
    >
      [{label}]
    </a>
  );
}
