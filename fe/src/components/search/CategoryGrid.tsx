// 진료과목·카테고리 둘러보기 그리드 — 닥터나우/모두닥/굿닥의 진료과 타일 패턴.
//
// 검색 랜딩(질의·카테고리 미선택)에서 "어떤 진료 분야를 볼까"를 한눈에 보여주는
// 아이콘 타일 그리드. 타일 클릭 → 그 카테고리 목록으로 드릴인(category 파라미터).
// 맨 앞 "전체 병원" 타일은 강남구 전체 목록으로 진입.
//
// /api/categories 응답 기반 2레벨 구조:
//   L1: specialty(표준 진료과) + etc(기타에서 승격된 버킷) 혼합, count 내림차순
//   L2: 세부 시술·증상 태그 — 부모 L1이 선택된 뒤 FocusChipBar 에서 노출

import type { ComponentType } from "react";
import {
  Activity,
  Baby,
  BedDouble,
  Bone,
  Brain,
  Building2,
  Cross,
  Droplet,
  Dumbbell,
  Ear,
  Eye,
  Flower2,
  HeartPulse,
  LayoutGrid,
  Leaf,
  Scale,
  Scissors,
  Smile,
  Sparkles,
  Stethoscope,
  Syringe,
  Wind,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { CategoryNode } from "@/types/domain";

type IconType = ComponentType<{ className?: string }>;

// 표준 진료과목(specialty) + etc 버킷 → 아이콘. 없으면 Stethoscope 기본값.
const CATEGORY_ICON: Record<string, IconType> = {
  // ── 표준 진료과 (origin: "specialty") ────────────────────────────────
  내과: Stethoscope,
  소아청소년과: Baby,
  이비인후과: Ear,
  안과: Eye,
  피부과: Sparkles,
  성형외과: Scissors,
  정형외과: Bone,
  신경외과: Brain,
  신경과: Activity,
  외과: Cross,
  산부인과: Flower2,
  비뇨의학과: Droplet,
  정신건강의학과: Brain,
  가정의학과: HeartPulse,
  재활의학과: Dumbbell,
  마취통증의학과: Syringe,
  한의원: Leaf,
  치과: Smile,
  종합병원: Building2,
  요양병원: BedDouble,
  보건소: Cross,
  // ── etc 버킷 (origin: "etc") — 기타에서 승격된 주력 분야 ─────────────
  미용: Sparkles,
  "모발·탈모": Scissors,
  "통증·근골격": Bone,
  "비만·다이어트": Scale,
  정신: Brain,
  수면: BedDouble,
  "비뇨·여성": Flower2,
  "피부·알레르기": Droplet,
  일반: Stethoscope,
  // ── 기타·레거시 ────────────────────────────────────────────────────
  기타: Wind,
};

interface CategoryGridProps {
  categories: CategoryNode[];
  totalHospitals: number;
  onSelect: (categoryKey: string) => void; // "" = 전체 병원
  isLoading?: boolean;
}

export function CategoryGrid({
  categories,
  totalHospitals,
  onSelect,
  isLoading,
}: CategoryGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="shimmer flex h-28 flex-col items-center justify-center rounded-xl border bg-card"
            aria-hidden
          />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
      {/* 전체 병원 타일 — 강조 톤 */}
      <Tile
        index={0}
        icon={LayoutGrid}
        label="전체 병원"
        count={totalHospitals}
        onClick={() => onSelect("")}
        primary
      />

      {categories.map((node, i) => (
        <Tile
          key={node.key}
          index={i + 1}
          icon={CATEGORY_ICON[node.key] ?? Stethoscope}
          label={node.key}
          count={node.count}
          onClick={() => onSelect(node.key)}
          isEtcBucket={node.origin === "etc"}
        />
      ))}
    </div>
  );
}

interface TileProps {
  index: number;
  icon: IconType;
  label: string;
  count: number;
  onClick: () => void;
  primary?: boolean;
  /** etc 버킷(기타에서 승격된 분야)은 미묘하게 다른 강조 색 적용 */
  isEtcBucket?: boolean;
}

function Tile({ index, icon: Icon, label, count, onClick, primary, isEtcBucket }: TileProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      // 진입: 아래에서 페이드+슬라이드, index 로 스태거. hover: 살짝 떠오름.
      style={{ animationDelay: `${Math.min(index, 16) * 35}ms` }}
      className={cn(
        "group flex flex-col items-center justify-center gap-2 rounded-xl border bg-card p-4 text-center shadow-sm",
        "animate-in fade-in slide-in-from-bottom-2 fill-mode-both duration-300",
        "transition-all hover:-translate-y-1 hover:border-primary/50 hover:shadow-md",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        primary && "border-primary/40 bg-primary/5",
        isEtcBucket && "border-violet-200/60 bg-violet-50/30",
      )}
    >
      <span
        className={cn(
          "flex h-11 w-11 items-center justify-center rounded-full transition-colors",
          primary
            ? "bg-primary/15 text-primary"
            : isEtcBucket
              ? "bg-violet-100 text-violet-600 group-hover:bg-violet-200/70 group-hover:text-violet-700"
              : "bg-accent text-accent-foreground group-hover:bg-primary/10 group-hover:text-primary",
        )}
      >
        <Icon className="h-5 w-5" />
      </span>
      <span className="text-sm font-semibold tracking-tight text-foreground">
        {label}
      </span>
      <span className="text-xs tabular-nums text-muted-foreground">
        {count.toLocaleString()}곳
      </span>
    </button>
  );
}
