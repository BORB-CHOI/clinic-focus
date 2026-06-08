import { Link } from "react-router-dom";
import { MapPin } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { HospitalThumbnail } from "@/components/common/HospitalThumbnail";
import { cn } from "@/lib/utils";
import type { SearchResultItem } from "@/types/domain";

interface HospitalCardProps {
  item: SearchResultItem;
  /**
   * 좁은 컨테이너(예: 지도 사이드 360px)에서 사용. 썸네일·패딩·폰트를
   * 한 단계 압축해 빽빽함을 줄인다. 검색 페이지의 본 카드는 compact 미사용.
   */
  compact?: boolean;
  className?: string;
}

// 검색 결과 카드 — 정보 위계
//
// 카드 좌측에 정사각 썸네일, 우측에 정보 위계 4단:
//   1) 표준 진료과목 + 주력 분야 태그       — 분류 미리보기. 시선 첫 진입
//   2) 병원명 + 신뢰도 배지                  — 큰 글씨 한 줄에 핵심
//   3) 위치 · 거리                           — 작은 메타
//   4) 한 줄 요약 (one_line_summary)         — ai_description 미리보기
//
// 썸네일은 BE 이미지 미구현이라 그라데이션 + 이니셜 플레이스홀더로 자리만 차지.
// 이미지 수집 로직 추가 시 thumbnail_url 만 채우면 자동 표시.
//
// "정보 부족" 등급 카드는 회색 톤·점선 보더로 시각 차이 — 의료법 주체 명시
// 원칙상 평가하지 않으나, 사용자가 한눈에 신뢰도 위계를 인지하도록 시각 위계는 보존.
export function HospitalCard({
  item,
  compact = false,
  className,
}: HospitalCardProps) {
  // 미분류(confidence=null) 병원도 카테고리·지도엔 노출된다 → null 안전 처리.
  const isLowConfidence = !item.confidence || item.confidence.level === "정보 부족";

  // 분류 태그 — 흰색(outline) 1개 = 진료과 라벨, 회색(secondary) N개 = 실제 주력 분야.
  // '기타' 병원은 라벨을 primary_focus 에서 파생(etc_subcategory)하는데, 그 파생값이
  // 주력 토큰과 글자까지 같으면(예: 모발·탈모) 흰색·회색에 같은 말이 두 번 찍힌다.
  // → 라벨과 동일한 주력 토큰은 회색에서 제거해 중복을 없앤다.
  const categoryLabel = item.etc_subcategory || item.standard_specialty;
  const focusTags = item.primary_focus.filter((f) => f !== categoryLabel);

  return (
    <Link
      to={`/hospitals/${item.hospital_id}`}
      aria-label={`${item.name} 상세 페이지로 이동`}
      className={cn(
        // 카드 내부 본문 사이즈는 컨테이너 폭에 맞춰 분기:
        //   - 일반(검색 페이지 max-w-screen-md): 0.8em
        //   - compact(지도 사이드 360px):        0.7em
        // 카드 내부 모든 자식이 em 으로 따라옴.
        "block rounded-lg border bg-card shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        compact ? "p-3 text-[0.7em]" : "p-4 text-[0.8em]",
        isLowConfidence && "border-dashed bg-muted/30",
        className,
      )}
    >
      <div className={cn("flex", compact ? "gap-2.5" : "gap-3")}>
        <HospitalThumbnail
          src={item.thumbnail_url}
          name={item.name}
          className={compact ? "h-14 w-14" : "h-20 w-20"}
        />

        <div className="min-w-0 flex-1">
          {/* 1) 분류 태그 — 표준 진료과목 + 주력 분야 */}
          <div className="flex flex-wrap items-center gap-1">
            <Badge variant="outline" className="font-normal">
              {categoryLabel}
            </Badge>
            {focusTags.length > 0
              ? focusTags
                  // compact 에선 첫 태그 하나만 (좁은 폭에 줄바꿈 방지)
                  .slice(0, compact ? 1 : focusTags.length)
                  .map((focus) => (
                    <Badge
                      key={focus}
                      variant="secondary"
                      className="font-normal"
                    >
                      {focus}
                    </Badge>
                  ))
              : // 주력이 라벨과 같아 회색 태그가 비는 경우(모발·탈모 등)는 라벨만으로 충분.
                // 원래 primary_focus 자체가 빈(분류는 됐으나 주력 미상) 병원만 점선 표시.
                item.primary_focus.length === 0 && (
                  <Badge
                    variant="outline"
                    className="border-dashed font-normal text-muted-foreground"
                  >
                    주력 미확정
                  </Badge>
                )}
          </div>

          {/* 2) 병원명 + 신뢰도 배지 */}
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
              {item.name}
            </h3>
            {item.confidence ? (
              <ConfidenceBadge confidence={item.confidence} />
            ) : (
              <span className="inline-flex shrink-0 items-center rounded-full border border-dashed border-input px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                미분류
              </span>
            )}
          </div>

          {/* 3) 위치 · 거리 메타 */}
          <p
            className={cn(
              "flex items-center gap-1 text-xs text-muted-foreground",
              compact ? "mt-0.5" : "mt-1",
            )}
          >
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
      </div>

      {/* 4) 한 줄 요약 — 본 서비스 차별점 (ai_description 미리보기)
          compact 모드에선 카드 세로를 줄이기 위해 숨김 (상세 페이지에서 노출) */}
      {!compact ? (
        <p
          className={cn(
            "mt-3 line-clamp-2 border-l-2 pl-3 text-[0.95em] leading-relaxed text-foreground",
            isLowConfidence ? "border-muted" : "border-primary/30",
          )}
        >
          {item.one_line_summary}
        </p>
      ) : null}
    </Link>
  );
}
