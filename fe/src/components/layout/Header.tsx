import { Link } from "react-router-dom";
import { Stethoscope, MapPin } from "lucide-react";

import { cn } from "@/lib/utils";

interface HeaderProps {
  /** 우측에 표시할 위치 라벨 (현재 동네). null 이면 "위치 미설정" */
  locationLabel?: string | null;
  className?: string;
}

// 글로벌 셸의 최상단 헤더.
// 로고 → 검색 페이지로 이동 (홈 동선).
// 우측 위치 라벨은 4단계 GPS·reverse geocoding 연결 전엔 placeholder.
export function Header({ locationLabel = null, className }: HeaderProps) {
  return (
    <header
      className={cn(
        "sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75",
        className,
      )}
    >
      <div className="container flex h-14 items-center justify-between gap-4">
        <Link
          to="/search"
          aria-label="clinic-focus 홈"
          className="flex items-center gap-2 text-base font-semibold tracking-tight"
        >
          <span
            aria-hidden
            className="grid h-7 w-7 place-items-center rounded-md bg-primary text-primary-foreground"
          >
            <Stethoscope className="h-4 w-4" />
          </span>
          <span>clinic-focus</span>
        </Link>

        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <MapPin className="h-3.5 w-3.5" aria-hidden />
          <span className="max-w-[12ch] truncate">
            {locationLabel ?? "위치 미설정"}
          </span>
        </div>
      </div>
    </header>
  );
}
