import { useState } from "react";
import { Link } from "react-router-dom";
import { Stethoscope, MapPin, UserRound } from "lucide-react";

import { HealthProfileModal } from "@/components/analytics/HealthProfileModal";
import { WeatherBadge } from "@/components/analytics/WeatherBadge";
import { hasHealthProfile } from "@/lib/healthProfile";
import { cn } from "@/lib/utils";

interface HeaderProps {
  locationLabel?: string | null;
  className?: string;
}

export function Header({ locationLabel = null, className }: HeaderProps) {
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

          <div className="flex items-center gap-3">
            {/* 내 정보 버튼 */}
            <button
              type="button"
              onClick={() => setProfileOpen(true)}
              aria-label="건강 프로파일 설정"
              className={cn(
                "relative flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors hover:border-primary/50 hover:text-foreground",
                hasProfile
                  ? "border-primary/30 bg-primary/5 text-primary"
                  : "border-input text-muted-foreground",
              )}
            >
              <UserRound className="h-3.5 w-3.5" aria-hidden />
              <span>{hasProfile ? "내 정보 수정" : "내 정보"}</span>
              {/* 미입력 시 주의 점 */}
              {!hasProfile && (
                <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-primary" />
              )}
            </button>

            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <MapPin className="h-3.5 w-3.5" aria-hidden />
              <span className="max-w-[12ch] truncate">
                {locationLabel ?? "위치 미설정"}
              </span>
            </div>

            <WeatherBadge compact />
          </div>
        </div>
      </header>

      <HealthProfileModal open={profileOpen} onClose={() => setProfileOpen(false)} />
    </>
  );
}
