import { Link } from "react-router-dom";
import { MapPin, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { HospitalThumbnail } from "@/components/common/HospitalThumbnail";
import { cn } from "@/lib/utils";
import { trackAdClick } from "@/lib/events";
import type { AdItem } from "@/types/ads";

interface AdCardProps {
  ad: AdItem;
  compact?: boolean;
  className?: string;
}

// 광고(협찬) 카드 — 유기적 HospitalCard 와 의도적으로 다른 톤.
//
// 의료법·광고 투명성: 좌상단 "광고" 라벨을 항상 노출하고, 앰버 보더+배경으로
// 자연 검색 결과와 시각 분리. 신뢰도 배지는 달지 않는다 (광고는 우리 분류·근거
// 강도 평가 대상이 아님). 카피는 "병원이 자기 사이트에서 ~로 표시" 주체 명시.
export function AdCard({ ad, compact = false, className }: AdCardProps) {
  const to = ad.hospital_id ? `/hospitals/${ad.hospital_id}` : null;
  const isExternal = !to && !!ad.landing_url;

  const handleClick = () => {
    trackAdClick(ad.ad_id, ad.hospital_id);
  };

  const inner = (
    <div className={cn("flex", compact ? "gap-2.5" : "gap-3")}>
      <HospitalThumbnail
        src={ad.thumbnail_url}
        name={ad.name}
        className={compact ? "h-14 w-14" : "h-20 w-20"}
      />

      <div className="min-w-0 flex-1">
        {/* 진료과 + 주력 태그 */}
        <div className="flex flex-wrap items-center gap-1">
          <Badge variant="outline" className="font-normal">
            {ad.standard_specialty}
          </Badge>
          {ad.primary_focus.map((focus) => (
            <Badge key={focus} variant="secondary" className="font-normal">
              {focus}
            </Badge>
          ))}
        </div>

        {/* 병원명 + 외부 링크 표시 */}
        <div
          className={cn(
            "flex items-start justify-between gap-2",
            compact ? "mt-1" : "mt-2",
          )}
        >
          <h3
            className={cn(
              "min-w-0 truncate font-semibold tracking-tight",
              compact ? "text-sm" : "text-base",
            )}
          >
            {ad.name}
          </h3>
          {isExternal ? (
            <ExternalLink
              className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground"
              aria-hidden
            />
          ) : null}
        </div>

        {/* 위치 */}
        <p
          className={cn(
            "flex items-center gap-1 text-xs text-muted-foreground",
            compact ? "mt-0.5" : "mt-1",
          )}
        >
          <MapPin className="h-3 w-3 shrink-0" aria-hidden />
          <span className="truncate">{ad.location_label}</span>
        </p>
      </div>
    </div>
  );

  const cardClass = cn(
    "relative block rounded-lg border border-amber-300/70 bg-amber-50/60 shadow-sm transition-all hover:-translate-y-0.5 hover:border-amber-400 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2",
    compact ? "p-3 text-[0.7em]" : "p-4 text-[0.8em]",
    className,
  );

  // "광고" 라벨 — 항상 노출, 우상단 고정
  const adLabel = (
    <span className="absolute right-2 top-2 z-10 rounded-full border border-amber-400 bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700">
      광고
    </span>
  );

  // 한 줄 카피 (주체 명시)
  const tagline =
    !compact && ad.tagline ? (
      <p className="mt-3 border-l-2 border-amber-300 pl-3 text-[0.95em] leading-relaxed text-foreground">
        {ad.tagline}
      </p>
    ) : null;

  if (to) {
    return (
      <Link
        to={to}
        onClick={handleClick}
        aria-label={`광고 — ${ad.name} 상세 페이지로 이동`}
        className={cardClass}
      >
        {adLabel}
        {inner}
        {tagline}
      </Link>
    );
  }

  if (isExternal) {
    return (
      <a
        href={ad.landing_url!}
        target="_blank"
        rel="noopener noreferrer sponsored"
        onClick={handleClick}
        aria-label={`광고 — ${ad.name} (외부 사이트로 이동)`}
        className={cardClass}
      >
        {adLabel}
        {inner}
        {tagline}
      </a>
    );
  }

  // 링크 없는 순수 노출 슬롯
  return (
    <div className={cardClass} aria-label={`광고 — ${ad.name}`}>
      {adLabel}
      {inner}
      {tagline}
    </div>
  );
}
