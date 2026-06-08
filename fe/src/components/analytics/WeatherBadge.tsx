import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";

interface WeatherData {
  temp_bucket:        string;
  feels_like_bucket:  string;
  temp_diff_bucket:   string;
  humidity_bucket:    string;
  pm25_bucket:        string;
  season:             string;
  time_bucket:        string;
  day_type:           string;
  temp_c:             number | null;
  feels_like_c:       number | null;
  temp_diff_c:        number | null;
  humidity_pct:       number | null;
  pm25_value:         number | null;
  wind_ms:            number | null;
  is_raining:         boolean;
  available:          boolean;
}

// ── 버킷 → 표시 텍스트 + 이모티콘 ──────────────────────────────────────────

const TEMP_MAP: Record<string, { emoji: string; label: string }> = {
  cold:    { emoji: "🥶", label: "추움" },
  cool:    { emoji: "🧥", label: "선선함" },
  mild:    { emoji: "🌤️", label: "쾌적함" },
  warm:    { emoji: "☀️", label: "따뜻함" },
  hot:     { emoji: "🔥", label: "더움" },
  unknown: { emoji: "🌡️", label: "—" },
};

const HUMIDITY_MAP: Record<string, { emoji: string; label: string }> = {
  dry:     { emoji: "🏜️", label: "건조" },
  normal:  { emoji: "💧", label: "보통" },
  humid:   { emoji: "💦", label: "습함" },
  unknown: { emoji: "💧", label: "—" },
};

const PM25_MAP: Record<string, { emoji: string; label: string; color: string }> = {
  good:     { emoji: "😊", label: "좋음",    color: "text-emerald-600" },
  moderate: { emoji: "🌫️", label: "보통",    color: "text-yellow-600" },
  bad:      { emoji: "😷", label: "나쁨",    color: "text-orange-600" },
  very_bad: { emoji: "🚨", label: "매우나쁨", color: "text-red-600" },
  unknown:  { emoji: "🌫️", label: "—",       color: "text-muted-foreground" },
};

function formatNumber(value: number | null | undefined, unit: string): string | null {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}${unit}` : null;
}

// ── 컴포넌트 ────────────────────────────────────────────────────────────────

// 강남역 기본 좌표 — 데이터(강남구) 기준, 헤더 날씨 기본값
const DEFAULT_LAT = 37.4979;
const DEFAULT_LNG = 127.0276;

interface Props {
  lat?: number;
  lng?: number;
  /** 헤더용 한 줄 compact 모드 */
  compact?: boolean;
}

export function WeatherBadge({ lat = DEFAULT_LAT, lng = DEFAULT_LNG, compact = false }: Props) {
  const { data, isLoading } = useQuery<{ data: WeatherData }>({
    queryKey: ["weather-v2", Math.round(lat * 100) / 100, Math.round(lng * 100) / 100],
    queryFn: ({ signal }) =>
      apiGet<{ data: WeatherData }>("/api/analytics/weather", { lat, lng }, signal),
    staleTime: 10 * 60 * 1000,
    refetchOnMount: "always",
    retry: false,
  });

  const w = data?.data;

  // ── compact (헤더용) ────────────────────────────────────────────────────
  if (compact) {
    if (isLoading || !w?.available) return null;
    const temp  = TEMP_MAP[w.temp_bucket]      ?? TEMP_MAP.unknown;
    const pm25  = PM25_MAP[w.pm25_bucket]      ?? PM25_MAP.unknown;
    const humid = HUMIDITY_MAP[w.humidity_bucket] ?? HUMIDITY_MAP.unknown;

    return (
      <div className="flex items-center gap-2 whitespace-nowrap text-xs">
        <span className="hidden text-muted-foreground/40 lg:inline" aria-hidden>|</span>
        <span className="hidden text-muted-foreground lg:inline">오늘의 날씨</span>
        {/* 온도 — 모바일 이모지만, sm+ 숫자도 노출 */}
        <span className="flex items-center gap-0.5 font-medium text-foreground">
          <span aria-hidden>{temp.emoji}</span>
          <span className="hidden sm:inline">{formatNumber(w.temp_c, "°C") ?? temp.label}</span>
        </span>
        {/* 습도·미세먼지 — 데스크톱(lg)부터만 */}
        <span className="hidden items-center gap-0.5 text-muted-foreground lg:flex">
          <span aria-hidden>{humid.emoji}</span>
          <span>{formatNumber(w.humidity_pct, "%") ?? humid.label}</span>
        </span>
        <span className={`hidden items-center gap-0.5 lg:flex ${pm25.color}`}>
          <span aria-hidden>{pm25.emoji}</span>
          <span>{pm25.label}</span>
        </span>
      </div>
    );
  }

  // ── 일반 (지도 페이지용) ────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="animate-pulse">날씨 불러오는 중…</span>
      </div>
    );
  }

  if (!w?.available) {
    return (
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">날씨 데이터</span>
        <span>기온 —</span>
        <span>습도 —</span>
        <span>초미세 —</span>
        <span>일교차 —</span>
      </div>
    );
  }

  const temp     = TEMP_MAP[w.temp_bucket]         ?? TEMP_MAP.unknown;
  const humidity = HUMIDITY_MAP[w.humidity_bucket] ?? HUMIDITY_MAP.unknown;
  const pm25     = PM25_MAP[w.pm25_bucket]         ?? PM25_MAP.unknown;

  return (
    <div className="flex items-center gap-x-3 text-xs overflow-x-auto">
      <span className="flex items-center gap-1 font-medium text-foreground shrink-0">
        <span aria-hidden>{w.is_raining ? "☔" : temp.emoji}</span>
        {formatNumber(w.temp_c, "°C") ?? temp.label}
        {w.feels_like_c != null && (
          <span className="font-normal text-muted-foreground">
            체감 {formatNumber(w.feels_like_c, "°C")}
          </span>
        )}
      </span>
      <span className="text-border shrink-0" aria-hidden>│</span>
      <span className="flex shrink-0 items-center gap-1 text-muted-foreground">
        <span aria-hidden>{humidity.emoji}</span>습도 {formatNumber(w.humidity_pct, "%") ?? humidity.label}
      </span>
      <span className="text-border shrink-0" aria-hidden>│</span>
      <span className={`flex shrink-0 items-center gap-1 ${pm25.color}`}>
        <span aria-hidden>{pm25.emoji}</span>초미세 {pm25.label}
        {w.pm25_value != null && (
          <span className="font-normal opacity-60">({formatNumber(w.pm25_value, "㎍/m³")})</span>
        )}
      </span>
      <span className="text-border shrink-0" aria-hidden>│</span>
      <span className="flex shrink-0 items-center gap-1 text-muted-foreground/50">
        <span aria-hidden>📊</span>일교차 {formatNumber(w.temp_diff_c, "°C") ?? "—"}
      </span>
      <span className="text-[10px] text-muted-foreground/40 shrink-0">실시간</span>
    </div>
  );
}
