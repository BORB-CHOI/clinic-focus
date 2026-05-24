import { Link } from "react-router-dom";
import { MapPin } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { cn } from "@/lib/utils";
import type { SearchResultItem } from "@/types/domain";

interface HospitalCardProps {
  item: SearchResultItem;
  className?: string;
}

// 검색 결과 카드 — 정보 위계 다듬기 라운드
//
// 정보 위계 (위 → 아래):
//   1) 표준 진료과목 + 주력 분야 태그       — 분류 미리보기. 시선 첫 진입
//   2) 병원명 + 신뢰도 배지                  — 큰 글씨 한 줄에 핵심
//   3) 위치 · 거리                           — 작은 메타
//   4) 한 줄 요약 (one_line_summary)         — ai_description 미리보기
//
// "정보 부족" 등급 카드는 회색 톤·점선 보더로 시각 차이 — 의료법 주체 명시
// 원칙상 평가하지 않으나, 사용자가 한눈에 신뢰도 위계를 인지하도록 시각 위계는 보존.
export function HospitalCard({ item, className }: HospitalCardProps) {
  const isLowConfidence = item.confidence.level === "정보 부족";

  return (
    <Link
      to={`/hospitals/${item.hospital_id}`}
      aria-label={`${item.name} 상세 페이지로 이동`}
      className={cn(
        // text-[0.8em] : 카드 내부 본문은 글로벌 base 의 80% 크기. 리스트
        // 가독성을 위해 한 단계 압축. 카드 내부 모든 자식이 em 으로 따라옴.
        "block rounded-lg border bg-card p-4 text-[0.8em] shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        isLowConfidence && "border-dashed bg-muted/30",
        className,
      )}
    >
      {/* 1) 분류 태그 — 표준 진료과목 + 주력 분야 */}
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant="outline" className="font-normal">
          {item.standard_specialty}
        </Badge>
        {item.primary_focus.length > 0 ? (
          item.primary_focus.map((focus) => (
            <Badge key={focus} variant="secondary" className="font-normal">
              {focus}
            </Badge>
          ))
        ) : (
          <Badge
            variant="outline"
            className="border-dashed font-normal text-muted-foreground"
          >
            주력 분야 정보 부족
          </Badge>
        )}
      </div>

      {/* 2) 병원명 + 신뢰도 배지 */}
      <div className="mt-2 flex items-start justify-between gap-3">
        <h3 className="min-w-0 truncate text-base font-semibold tracking-tight">
          {item.name}
        </h3>
        <ConfidenceBadge confidence={item.confidence} />
      </div>

      {/* 3) 위치 · 거리 메타 */}
      <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
        <MapPin className="h-3 w-3 shrink-0" aria-hidden />
        <span className="truncate">
          {item.location.sigungu}
          {item.location.dong ? ` · ${item.location.dong}` : ""}
        </span>
        {item.distance_km !== null ? (
          <>
            <span aria-hidden>·</span>
            <span className="font-mono">
              {item.distance_km.toFixed(1)}km
            </span>
          </>
        ) : null}
      </p>

      {/* 4) 한 줄 요약 — 본 서비스 차별점 (ai_description 미리보기) */}
      <p
        className={cn(
          "mt-3 line-clamp-2 border-l-2 pl-3 text-[0.95em] leading-relaxed text-foreground",
          isLowConfidence ? "border-muted" : "border-primary/30",
        )}
      >
        {item.one_line_summary}
      </p>
    </Link>
  );
}
