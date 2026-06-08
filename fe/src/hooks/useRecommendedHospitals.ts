import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/lib/api";
import { getDeviceId } from "@/lib/device";
import { getContextReason, sortHospitalsByAgefit } from "@/lib/recommendReason";
import type { SearchResultItem } from "@/types/domain";

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

interface ProfileData { gender_bucket: string; age_bucket: string }
interface SegmentRow  { label: string; count: number }
interface CohortRow   { label: string; count: number; segments: SegmentRow[] }
interface WeatherData {
  pm25_bucket: string; temp_bucket: string; temp_diff_bucket: string;
  humidity_bucket: string; is_raining: boolean; available: boolean;
}
interface InsightsData {
  current_season?: string;
  charts: {
    age_gender_by_specialty: CohortRow[];
    top_specialties: SegmentRow[];
  };
}

export interface RecommendedHospitalsResult {
  hospitals: SearchResultItem[];
  cohortLabel: string | null;
  topSpecialty: string | null;
  reasonText: string | null;
  contextReason: string | null;
  isLoading: boolean;
}

export function useRecommendedHospitals(): RecommendedHospitalsResult {
  const deviceId = getDeviceId();

  const { data: profileRes } = useQuery<{ data: ProfileData } | null>({
    queryKey: ["analytics-profile", deviceId],
    queryFn: ({ signal }) =>
      apiGet<{ data: ProfileData }>("/api/analytics/profile", { device_id: deviceId }, signal)
        .catch(() => null),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const { data: insightsRes } = useQuery<{ data: InsightsData }>({
    queryKey: ["analytics-insights-recommend"],
    queryFn: ({ signal }) =>
      apiGet<{ data: InsightsData }>("/api/analytics/insights", {}, signal),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  const { data: weatherRes } = useQuery<{ data: WeatherData }>({
    queryKey: ["weather-v2", DEFAULT_LAT, DEFAULT_LNG],
    queryFn: ({ signal }) =>
      apiGet<{ data: WeatherData }>("/api/analytics/weather", { lat: DEFAULT_LAT, lng: DEFAULT_LNG }, signal),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  const profile   = profileRes?.data ?? null;
  const insights  = insightsRes?.data;
  const weather   = weatherRes?.data?.available ? weatherRes.data : null;
  const season    = insights?.current_season ?? null;

  let specialties: SegmentRow[] = [];
  let cohortLabel: string | null = null;

  if (profile && insights?.charts) {
    const key = `${profile.age_bucket}#${profile.gender_bucket}`;
    const row  = insights.charts.age_gender_by_specialty?.find((r) => r.label === key);
    if (row?.segments?.length) {
      specialties = row.segments.slice(0, 3);
      const age    = AGE_LABEL[profile.age_bucket]    ?? profile.age_bucket;
      const gender = GENDER_LABEL[profile.gender_bucket] ?? "";
      cohortLabel  = `${age} ${gender}이 요즘 많이 찾아요`;
    }
  }

  if (specialties.length === 0 && insights?.charts) {
    specialties = (insights.charts.top_specialties ?? []).slice(0, 3);
    cohortLabel  = "요즘 강남구에서 많이 찾아요";
  }

  const topSpecialty = specialties[0]?.label ?? null;

  // 기본 추천 근거 (프로필 기반)
  const reasonText = topSpecialty
    ? profile
      ? `내 프로필(${AGE_LABEL[profile.age_bucket] ?? profile.age_bucket} ${GENDER_LABEL[profile.gender_bucket] ?? ""})과 비슷한 분들이 강남구에서 ${topSpecialty}를 가장 많이 찾았어요!`
      : `최근 강남구에서 사람들이 ${topSpecialty}를 가장 많이 검색했어요 🙂`
    : null;

  // 필터링을 위해 limit 6으로 받아 연령 적합도 순 정렬 후 3개 사용
  const { data: hospitalsRes, isLoading } = useQuery<{ data: SearchResultItem[] }>({
    queryKey: ["recommend-hospitals", topSpecialty],
    queryFn: ({ signal }) =>
      apiGet<{ data: SearchResultItem[] }>("/api/search", {
        specialty: topSpecialty,
        sigungu:   POC_SIGUNGU,
        sort:      "confidence",
        limit:     6,
      }, signal),
    enabled: !!topSpecialty,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  // 계절·날씨 + 키워드 기반 맥락 이유 (hospitalsRes 로드 후 topFocus 계산)
  const topFocus = (hospitalsRes?.data?.[0]?.primary_focus ?? []) as string[];
  const contextReason = topSpecialty
    ? getContextReason(topSpecialty, season, weather, topFocus)
    : null;

  const hospitals = useMemo(
    () => sortHospitalsByAgefit(hospitalsRes?.data ?? [], profile?.age_bucket ?? null, 3),
    [hospitalsRes, profile?.age_bucket],
  );

  return {
    hospitals,
    cohortLabel,
    topSpecialty,
    reasonText,
    contextReason,
    isLoading: isLoading && !!topSpecialty,
  };
}
