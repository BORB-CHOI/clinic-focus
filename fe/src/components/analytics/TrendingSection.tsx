import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { TrendingUp } from "lucide-react";
import { apiGet } from "@/lib/api";

interface SpecialtyRow {
  label: string;
  count: number;
}

interface InsightsData {
  specialty_by_season: SpecialtyRow[] | null;
  current_season: string;
}

const SEASON_LABEL: Record<string, string> = {
  spring: "봄",
  summer: "여름",
  fall: "가을",
  winter: "겨울",
};

// browse 홈 — 현재 계절에 많이 찾은 진료과목 상위 칩 표시.
// Analytics 인사이트 기반. 데이터 미충족(k-anonymity < 5)이면 섹션 숨김.
export function TrendingSection() {
  const { data, isLoading } = useQuery<{ data: InsightsData }>({
    queryKey: ["analytics-insights-trending"],
    queryFn: ({ signal }) =>
      apiGet<{ data: InsightsData }>("/api/analytics/insights", {}, signal),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  if (isLoading) return null;

  const rows = data?.data?.specialty_by_season ?? [];
  const season = data?.data?.current_season ?? "";
  const top = rows.slice(0, 5);

  if (top.length === 0) return null;

  return (
    <section className="space-y-2">
      <div className="flex items-center gap-1.5">
        <TrendingUp className="h-4 w-4 text-primary" aria-hidden />
        <h2 className="text-sm font-semibold tracking-tight">
          {SEASON_LABEL[season] ?? "이번 시즌"} 많이 찾는 진료과
        </h2>
      </div>
      <div className="flex flex-wrap gap-2">
        {top.map((row) => (
          <Link
            key={row.label}
            to={`/search?specialty=${encodeURIComponent(row.label)}`}
            className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary transition-colors hover:border-primary/40 hover:bg-primary/10"
          >
            {row.label}
            <span className="text-[10px] text-primary/60">{row.count}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
