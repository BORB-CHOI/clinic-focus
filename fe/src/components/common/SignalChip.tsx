import { cn } from "@/lib/utils";
import { SIGNAL_LABEL, detailedSignalAnchorId } from "@/lib/signals";
import type { SignalKey } from "@/types/domain";

interface SignalChipProps {
  signal: SignalKey;
  className?: string;
}

// citations 배지 — 클릭 시 상세 페이지 ④ detailed_signals 해당 섹션으로 스크롤
// public_data는 detailed_signals에 없으므로 클릭 비활성
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
        "inline-flex items-center rounded border bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
        className,
      )}
    >
      [{label}]
    </a>
  );
}
