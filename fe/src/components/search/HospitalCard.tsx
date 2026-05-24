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

// 검색 결과 카드 — `<Link>`로 카드 전체가 상세 페이지 진입점
// 의료법 주체 명시: one_line_summary 본문은 BE/AI가 통제 (FE는 그대로 노출)
// Tag: standard_specialty=outline, primary_focus=secondary 로 시각 구분
export function HospitalCard({ item, className }: HospitalCardProps) {
  return (
    <Link
      to={`/hospitals/${item.hospital_id}`}
      className={cn(
        // text-[0.8em] : 카드 내부 본문은 글로벌 base 의 80% 크기. 리스트
        // 가독성을 위해 한 단계 압축. 카드 내부 모든 자식이 em 으로 따라옴.
        "block rounded-lg border bg-card p-4 text-[0.8em] transition-colors hover:border-primary/40 hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold">{item.name}</h3>
          <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
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
        </div>
        <ConfidenceBadge confidence={item.confidence} />
      </div>

      <p className="mt-3 line-clamp-2 text-sm text-foreground">
        {item.one_line_summary}
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
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
    </Link>
  );
}
