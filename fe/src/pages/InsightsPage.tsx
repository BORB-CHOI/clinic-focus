import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, UserCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { HealthProfileModal } from "@/components/analytics/HealthProfileModal";
import { getHealthProfile } from "@/lib/healthProfile";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";

// ── 레이블 맵 ──────────────────────────────────────────────────────────────

const SEASON_KO: Record<string, string> = {
  spring: "봄", summer: "여름", fall: "가을", winter: "겨울",
};
const SEASON_EMOJI: Record<string, string> = {
  spring: "🌸", summer: "☀️", fall: "🍂", winter: "❄️",
};
const TIME_KO: Record<string, string> = {
  dawn: "새벽", morning: "오전", afternoon: "오후", evening: "저녁",
};
const TIME_EMOJI: Record<string, string> = {
  dawn: "🌙", morning: "🌅", afternoon: "🌞", evening: "🌆",
};
const AGE_KO: Record<string, string> = {
  teens: "10대", "20s": "20대", "30s": "30대", "40s": "40대", "50plus": "50대+",
};
const GENDER_KO: Record<string, string> = {
  male: "남성", female: "여성", other: "기타",
};
const SPECIALTY_PALETTE: Record<string, string> = {
  "피부과":     "bg-rose-100 text-rose-700",
  "이비인후과": "bg-sky-100 text-sky-700",
  "성형외과":   "bg-purple-100 text-purple-700",
  "내과":       "bg-emerald-100 text-emerald-700",
  "정형외과":   "bg-amber-100 text-amber-700",
  "기타":       "bg-slate-100 text-slate-600",
};
const FALLBACK_PALETTE = [
  "bg-indigo-100 text-indigo-700",
  "bg-teal-100 text-teal-700",
  "bg-orange-100 text-orange-700",
  "bg-pink-100 text-pink-700",
];

// ── 타입 ───────────────────────────────────────────────────────────────────

interface Segment {
  label: string;
  count: number;
}

interface Row {
  label: string;
  count: number;
  segments?: Segment[];
}

interface InsightsData {
  source_event_count: number;
  k_anonymity: number;
  current_season?: string;
  current_time_bucket?: string;
  charts: {
    specialty_by_season?: Row[];
    specialty_by_time?: Row[];
    age_by_specialty?: Row[];
    age_gender_by_specialty?: Row[];
  };
}

// ── 서브컴포넌트 ───────────────────────────────────────────────────────────

function InsightCard({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-xl border bg-card p-5", className)}>
      <div className="mb-4">
        <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        {subtitle && (
          <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
        )}
      </div>
      {children}
    </section>
  );
}

function RankedList({
  segments,
  totalCount,
}: {
  segments: Segment[];
  totalCount: number;
}) {
  const max = Math.max(1, ...segments.map((s) => s.count));
  return (
    <div className="space-y-3">
      {segments.map((seg, i) => {
        const pct = totalCount > 0 ? Math.round((seg.count / totalCount) * 100) : 0;
        return (
          <div key={seg.label} className="flex items-center gap-3">
            <span className="w-3 shrink-0 text-right text-[11px] text-muted-foreground">
              {i + 1}
            </span>
            <span className="w-20 shrink-0 text-sm">{seg.label}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${Math.max(4, (seg.count / max) * 100)}%` }}
              />
            </div>
            <span className="w-7 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
              {pct}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

function SpecialtyPill({
  label,
  pct,
  index,
}: {
  label: string;
  pct: number;
  index: number;
}) {
  const color =
    SPECIALTY_PALETTE[label] ?? FALLBACK_PALETTE[index % FALLBACK_PALETTE.length];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
        color,
      )}
    >
      {label}
      <span className="opacity-60">{pct}%</span>
    </span>
  );
}

function EmptyRows() {
  return (
    <p className="py-6 text-center text-xs text-muted-foreground">
      k 기준을 통과한 데이터가 아직 없습니다.
    </p>
  );
}

// ── 메인 ───────────────────────────────────────────────────────────────────

export default function InsightsPage() {
  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profile, setProfile] = useState(() => getHealthProfile());

  const { data, isLoading, isError } = useQuery<{ data: InsightsData }>({
    queryKey: ["analytics-insights"],
    queryFn: ({ signal }) =>
      apiGet<{ data: InsightsData }>("/api/analytics/insights", undefined, signal),
    staleTime: 60 * 1000,
    retry: false,
  });

  const insights = data?.data;
  const hasData = (insights?.source_event_count ?? 0) > 0;

  async function refresh() {
    setRefreshing(true);
    try {
      const next = await apiGet<{ data: InsightsData }>("/api/analytics/insights", {
        refresh: true,
      });
      queryClient.setQueryData(["analytics-insights"], next);
    } finally {
      setRefreshing(false);
    }
  }

  const currentSeason = insights?.current_season ?? "unknown";
  const currentTime = insights?.current_time_bucket ?? "unknown";

  const seasonRows = insights?.charts?.specialty_by_season ?? [];
  const currentSeasonRow = seasonRows.find((r) => r.label === currentSeason);

  const ageRows = insights?.charts?.age_by_specialty ?? [];
  const ageGenderRows = insights?.charts?.age_gender_by_specialty ?? [];

  const profileKey = `${profile.ageBucket}#${profile.genderBucket}`;
  const profileLabel = [AGE_KO[profile.ageBucket], GENDER_KO[profile.genderBucket]]
    .filter(Boolean)
    .join(" ");
  const hasProfile = profile.ageBucket !== "unknown" && profile.genderBucket !== "unknown";
  const myRow = ageGenderRows.find((r) => r.label === profileKey);

  const timeRows = insights?.charts?.specialty_by_time ?? [];
  const currentTimeRow = timeRows.find((r) => r.label === currentTime);

  return (
    <section className="space-y-5">
      {/* 헤더 */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">수요 인사이트</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            검색·환경 컨텍스트로 읽는 진료 수요 신호
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={refresh}
          disabled={refreshing}
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} aria-hidden />
          재집계
        </Button>
      </div>

      {/* 상태별 렌더 */}
      {isLoading ? (
        <div className="rounded-xl border bg-card p-5 text-sm text-muted-foreground">
          불러오는 중...
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          인사이트를 불러오지 못했습니다.
        </div>
      ) : !insights || !hasData ? (
        <EmptyInsights />
      ) : (
        <div className="space-y-4">
          {/* 상단 2열: 계절 카드 + 연령 카드 */}
          <div className="grid gap-4 sm:grid-cols-2">
            {/* 카드 1: 이 계절에 많이 찾는 진료과 */}
            <InsightCard
              title={`${SEASON_EMOJI[currentSeason] ?? "🗓️"} ${SEASON_KO[currentSeason] ?? currentSeason}에 많이 찾는 진료과`}
              subtitle={
                currentSeasonRow
                  ? `${currentSeasonRow.count.toLocaleString()}건 기반`
                  : "재집계가 필요합니다"
              }
            >
              {currentSeasonRow?.segments?.length ? (
                <RankedList
                  segments={currentSeasonRow.segments}
                  totalCount={currentSeasonRow.count}
                />
              ) : (
                <EmptyRows />
              )}
            </InsightCard>

            {/* 카드 2: 내 연령대·성별 기반 */}
            <InsightCard
              title={
                hasProfile && myRow
                  ? `👤 ${profileLabel}이 많이 찾는 진료과`
                  : "👤 나와 비슷한 분들이 많이 찾는 진료과"
              }
              subtitle={myRow ? `${myRow.count.toLocaleString()}건 기반` : undefined}
            >
              {hasProfile && myRow ? (
                <>
                  <RankedList segments={myRow.segments ?? []} totalCount={myRow.count} />
                  <button
                    type="button"
                    onClick={() => setProfileOpen(true)}
                    className="mt-4 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                  >
                    <UserCircle className="h-3.5 w-3.5" />
                    내 정보 수정
                  </button>
                </>
              ) : (
                <div className="flex flex-col items-start gap-3 py-2">
                  <p className="text-sm text-muted-foreground">
                    {hasProfile
                      ? `${profileLabel} 데이터가 아직 충분하지 않습니다.`
                      : "연령대·성별을 설정하면 비슷한 분들의 진료 패턴을 볼 수 있어요."}
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setProfileOpen(true)}
                  >
                    <UserCircle className="mr-1.5 h-3.5 w-3.5" />
                    {hasProfile ? "내 정보 수정" : "내 정보 설정하기"}
                  </Button>
                </div>
              )}
            </InsightCard>
          </div>

          {/* 하단 전체폭: 지금 이 시간대 */}
          <InsightCard
            title={`${TIME_EMOJI[currentTime] ?? "🕐"} 지금 ${TIME_KO[currentTime] ?? currentTime}에 많이 찾는 진료과`}
            subtitle={
              currentTimeRow
                ? `${currentTimeRow.count.toLocaleString()}건 기반`
                : "재집계가 필요합니다"
            }
          >
            {currentTimeRow?.segments?.length ? (
              <div className="sm:max-w-sm">
                <RankedList
                  segments={currentTimeRow.segments}
                  totalCount={currentTimeRow.count}
                />
              </div>
            ) : (
              <EmptyRows />
            )}
          </InsightCard>
        </div>
      )}

      <HealthProfileModal
        open={profileOpen}
        onClose={() => {
          setProfileOpen(false);
          setProfile(getHealthProfile());
        }}
      />
    </section>
  );
}

function EmptyInsights() {
  return (
    <div className="rounded-xl border bg-card p-6">
      <h2 className="text-base font-semibold">아직 표시할 집계가 없습니다</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        이벤트가 쌓인 뒤 재집계를 누르거나, 데모 시드 스크립트로 가상 이벤트를 먼저 넣어볼 수 있습니다.
      </p>
      <code className="mt-4 block rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
        python -m be.scripts.seed_demo_analytics_events --count 180
      </code>
    </div>
  );
}
