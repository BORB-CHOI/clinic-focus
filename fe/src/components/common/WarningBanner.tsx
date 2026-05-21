import { AlertTriangle } from "lucide-react";

import { cn } from "@/lib/utils";

interface WarningBannerProps {
  message: string;
  className?: string;
}

// metadata.warning 노출용 배너 — fe/CLAUDE.md 명시
export function WarningBanner({ message, className }: WarningBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <p>{message}</p>
    </div>
  );
}
