import * as React from "react";

import { cn } from "@/lib/utils";

interface SectionProps {
  id?: string;
  title: string;
  subtitle?: string;
  /** 영역 번호 ① ~ ⑨ */
  badge?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

// 9영역 공통 셸. 영역 번호 + 제목 + 본문
export function Section({
  id,
  title,
  subtitle,
  badge,
  action,
  className,
  children,
}: SectionProps) {
  return (
    <section
      id={id}
      className={cn("scroll-mt-20 rounded-lg border bg-card p-6", className)}
    >
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            {badge ? (
              <span className="text-xs font-mono text-muted-foreground">
                {badge}
              </span>
            ) : null}
            <h2 className="text-lg font-semibold">{title}</h2>
          </div>
          {subtitle ? (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </header>
      {children}
    </section>
  );
}
