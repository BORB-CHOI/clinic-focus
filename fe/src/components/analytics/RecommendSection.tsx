import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { apiGet } from "@/lib/api";
import { getDeviceId } from "@/lib/device";
import { HospitalCard } from "@/components/search/HospitalCard";
import type { SearchResultItem } from "@/types/domain";

// ── 상수 ────────────────────────────────────────────────────────────────────

const DEFAULT_LAT = 37.5665;
const DEFAULT_LNG = 126.978;
const POC_SIGUNGU = "강남구";

const AGE_LABEL: Record<string, string> = {
  teens: "10대", "20s": "20대", "30s": "30대",
  "40s": "40대", "50plus": "50대 이상",
};
const GENDER_LABEL: Record<string, string> = {
  male: "남성", female: "여성",
};

// ── 날씨 기반 어드바이저리 ────────────────────────────────────────────────

interface WeatherCtx {
  season: string;
  temp_bucket: string;
  temp_diff_bucket: string;
  pm25_bucket: string;
  humidity_bucket: string;
  temp_diff_c: number | null;
  is_raining: boolean;
}

function getAdvisory(w: WeatherCtx): { icon: string; text: string } | null {
  if (w.is_raining)
    return { icon: "☔", text: "비가 오고 있어요. 우산 챙기고 감기 조심하세요!" };
  if ((w.season === "winter" || w.season === "fall") && ["cold", "cool"].includes(w.temp_bucket))
    return { icon: "🤧", text: "기온이 뚝 떨어졌어요. 감기 조심하세요!" };
  if (["large", "very_large"].includes(w.temp_diff_bucket))
    return { icon: "🌡️", text: `일교차가${w.temp_diff_c != null ? ` ${w.temp_diff_c.toFixed(0)}°C` : ""} 커요. 환절기 건강 관리 주의하세요!` };
  if (["bad", "very_bad"].includes(w.pm25_bucket))
    return { icon: "😷", text: "미세먼지가 나빠요. 외출 시 마스크를 챙기세요!" };
  if (w.season === "summer" && w.humidity_bucket === "humid")
    return { icon: "☀️", text: "덥고 습한 날씨예요. 피부 트러블 조심하세요!" };
  return null;
}

// ── 타입 ────────────────────────────────────────────────────────────────────

interface ProfileData { gender_bucket: string; age_bucket: string }
interface SegmentRow  { label: string; count: number }
interface CohortRow   { label: string; count: number; segments: SegmentRow[] }
interface InsightsData {
  charts: {
    age_gender_by_specialty: CohortRow[];
    top_specialties: SegmentRow[];
  };
}

// ── 컴포넌트 ────────────────────────────────────────────────────────────────

export function RecommendSection() {
  const deviceId = getDeviceId();

  // 1) 프로필 조회 (opt-in, 없으면 404 → null)
  const { data: profileRes } = useQuery<{ data: ProfileData } | null>({
    queryKey: ["analytics-profile", deviceId],
    queryFn: ({ signal }) =>
      apiGet<{ data: ProfileData }>("/api/analytics/profile", { device_id: deviceId }, signal)
        .catch(() => null),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  // 2) 인사이트 (코호트별 진료과 통계)
  const { data: insightsRes } = useQuery<{ data: InsightsData }>({
    queryKey: ["analytics-insights-recommend"],
    queryFn: ({ signal }) =>
      apiGet<{ data: InsightsData }>("/api/analytics/insights", {}, signal),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  // 3) 날씨 (어드바이저리용)
  const { data: weatherRes } = useQuery<{ data: WeatherCtx }>({
    queryKey: ["weather-v2", DEFAULT_LAT, DEFAULT_LNG],
    queryFn: ({ signal }) =>
      apiGet<{ data: WeatherCtx }>("/api/analytics/weather", { lat: DEFAULT_LAT, lng: DEFAULT_LNG }, signal),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  // ── 코호트 계산 ────────────────────────────────────────────────────────

  const profile  = profileRes?.data ?? null;
  const insights = insightsRes?.data?.charts;
  const weather  = weatherRes?.data ?? null;

  // 프로필이 있으면 코호트 매칭, 없으면 전체 인기 순위 사용
  let specialties: SegmentRow[] = [];
  let cohortLabel: string | null = null;

  if (profile && insights) {
    const key = `${profile.age_bucket}#${profile.gender_bucket}`;
    const row  = insights.age_gender_by_specialty?.find((r) => r.label === key);
    if (row?.segments?.length) {
      specialties = row.segments.slice(0, 3);
      const age    = AGE_LABEL[profile.age_bucket]    ?? profile.age_bucket;
      const gender = GENDER_LABEL[profile.gender_bucket] ?? "";
      cohortLabel = `${age} ${gender}이 요즘 많이 찾아요`;
    }
  }

  if (specialties.length === 0 && insights) {
    specialties = (insights.top_specialties ?? []).slice(0, 3);
    cohortLabel = "요즘 강남구에서 많이 찾아요";
  }

  const topSpecialty = specialties[0]?.label ?? null;
  const advisory     = weather ? getAdvisory(weather) : null;

  // 4) 추천 병원 3개 (top specialty 기준)
  const { data: hospitalsRes } = useQuery<{ data: SearchResultItem[] }>({
    queryKey: ["recommend-hospitals", topSpecialty],
    queryFn: ({ signal }) =>
      apiGet<{ data: SearchResultItem[] }>("/api/search", {
        specialty: topSpecialty,
        sigungu:   POC_SIGUNGU,
        sort:      "confidence",
        limit:     3,
      }, signal),
    enabled: !!topSpecialty,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const hospitals = hospitalsRes?.data ?? [];

  if (specialties.length === 0) return null;

  return (
    <section className="space-y-3 rounded-lg border bg-card p-4 shadow-sm">
      {/* 헤더 */}
      <div className="flex items-center gap-1.5">
        <Sparkles className="h-4 w-4 text-primary" aria-hidden />
        <h2 className="text-sm font-semibold tracking-tight">{cohortLabel}</h2>
      </div>

      {/* 진료과 키워드 칩 */}
      <div className="flex flex-wrap gap-2">
        {specialties.map((s) => (
          <Link
            key={s.label}
            to={`/search?specialty=${encodeURIComponent(s.label)}`}
            className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary transition-colors hover:border-primary/40 hover:bg-primary/10"
          >
            {s.label}
            <span className="text-[10px] text-primary/60">{s.count}</span>
          </Link>
        ))}
      </div>

      {/* 날씨 어드바이저리 */}
      {advisory && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span aria-hidden>{advisory.icon}</span>
          {advisory.text}
        </p>
      )}

      {/* 추천 병원 3개 */}
      {hospitals.length > 0 && (
        <div className="space-y-2 pt-1">
          <p className="text-xs font-medium text-muted-foreground">
            {topSpecialty} 추천 병원
          </p>
          <div className="space-y-2">
            {hospitals.map((item) => (
              <HospitalCard key={item.hospital_id} item={item} compact />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
