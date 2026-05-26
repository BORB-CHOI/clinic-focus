import { useNavigate } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

import { cn } from "@/lib/utils";

interface BackHeaderProps {
  /** 헤더에 표시할 라벨 (없으면 "뒤로") */
  title?: string | null;
  className?: string;
}

// 상세 페이지처럼 한 곳에 집중해야 하는 화면용 헤더.
// 검색바·토글 대신 좌측 ← 와 라벨만 노출 — 굿닥/모두닥 상세 페이지 패턴.
export function BackHeader({ title, className }: BackHeaderProps) {
  const navigate = useNavigate();

  return (
    <div
      className={cn(
        "sticky top-14 z-20 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75",
        className,
      )}
    >
      <div className="container flex h-12 items-center gap-2">
        <button
          type="button"
          aria-label="뒤로가기"
          onClick={() => {
            // 직접 진입 시 history 가 비어있을 수 있어 안전망: /search 로 폴백
            if (window.history.length > 1) navigate(-1);
            else navigate("/search");
          }}
          className="-ml-1 inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <ChevronLeft className="h-5 w-5" aria-hidden />
        </button>
        <span className="truncate text-sm font-medium">
          {title ?? "뒤로"}
        </span>
      </div>
    </div>
  );
}
