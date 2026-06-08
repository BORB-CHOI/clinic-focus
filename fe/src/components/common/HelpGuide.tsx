import { useEffect, useRef, useState } from "react";
import { CircleHelp, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface GuideStep {
  icon: string;
  label: string;
  text: string;
}

interface HelpGuideProps {
  steps: GuideStep[];
  align?: "left" | "right";
}

export function HelpGuide({ steps, align = "right" }: HelpGuideProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="사용 방법 안내"
        aria-expanded={open}
        className={cn(
          "flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-medium whitespace-nowrap",
          "text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary",
          open && "border-primary/40 text-primary bg-primary/5",
        )}
      >
        <CircleHelp className="h-3.5 w-3.5" aria-hidden />
        사용법
      </button>

      {open && (
        <div
          className={cn(
            "absolute top-8 z-50 w-72 rounded-xl border bg-card shadow-xl",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          <div className="flex items-center justify-between border-b px-4 py-3">
            <p className="text-sm font-semibold">이렇게 사용해 보세요</p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="rounded-md p-0.5 text-muted-foreground hover:text-foreground"
              aria-label="닫기"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <ol className="divide-y">
            {steps.map((step, i) => (
              <li key={i} className="flex gap-3 px-4 py-3">
                <span className="mt-0.5 text-base shrink-0">{step.icon}</span>
                <div>
                  <p className="text-xs font-semibold text-foreground">{step.label}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
