import { useState } from "react";
import { Link } from "react-router-dom";
import { UserRound } from "lucide-react";

import { HealthProfileModal } from "@/components/analytics/HealthProfileModal";
import { WeatherBadge } from "@/components/analytics/WeatherBadge";
import { LocationSearchBar } from "@/components/layout/LocationSearchBar";
import { hasHealthProfile } from "@/lib/healthProfile";
import { cn } from "@/lib/utils";

interface HeaderProps {
  className?: string;
}

export function Header({ className }: HeaderProps) {
  const [profileOpen, setProfileOpen] = useState(false);
  const hasProfile = hasHealthProfile();

  return (
    <>
      <header
        className={cn(
          "sticky top-0 z-30 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75",
          className,
        )}
      >
        <div className="container flex h-14 items-center justify-between gap-4">
          <Link
            to="/map"
            aria-label="clinic-focus 홈"
            className="flex items-center gap-2 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <img
              src="/logo.svg"
              alt="clinic-focus"
              className="h-9 w-auto"
              width={180}
              height={40}
            />
          </Link>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* 내 정보 버튼.
                - 위치바 없는 화면(리스트 등): 모바일에서도 라벨 노출 (여유 있음)
                - 지도 화면(위치바 동반): 모바일은 아이콘만, sm+ 라벨.
                  640~710px 빡빡 구간에서 두 줄로 안 깨지게 nowrap + 한 톤 작게 */}
            {/* 내 정보 버튼.
                - 위치바 없는 화면(리스트 등): 모바일에서도 라벨 노출 (여유 있음)
                - 지도 화면(위치바 동반):
                    모바일(<640) 아이콘만 / 태블릿(640~1023) "내 정보"
                    / 데스크톱(1024+) "내 정보 수정" */}
            <button
              type="button"
              onClick={() => setProfileOpen(true)}
              aria-label={hasProfile ? "내 정보 수정" : "내 정보 설정"}
              className={cn(
                "relative flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-1 text-xs transition-colors hover:border-primary/50 hover:text-foreground sm:px-2.5",
                hasProfile
                  ? "border-primary/30 bg-primary/5 text-primary"
                  : "border-input text-muted-foreground",
              )}
            >
              <UserRound className="h-3.5 w-3.5 shrink-0" aria-hidden />
              {hasProfile ? (
                <span className="hidden sm:inline">
                  내 정보<span className="hidden lg:inline"> 수정</span>
                </span>
              ) : (
                <span className="hidden sm:inline">내 정보</span>
              )}
              {/* 미입력 시 주의 점 */}
              {!hasProfile && (
                <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-primary" />
              )}
            </button>

            <LocationSearchBar />

            <WeatherBadge compact />
          </div>
        </div>
      </header>

      <HealthProfileModal open={profileOpen} onClose={() => setProfileOpen(false)} />
    </>
  );
}
