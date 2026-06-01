// 진료과목 둘러보기 그리드 — 닥터나우/모두닥/굿닥의 진료과 타일 패턴.
//
// 검색 랜딩(질의·진료과 미선택)에서 "어떤 진료과를 볼까"를 한눈에 보여주는
// 아이콘 타일 그리드. 타일 클릭 → 그 진료과 목록으로 드릴인(specialty 파라미터).
// 맨 앞 "전체 병원" 타일은 강남구 전체 목록으로 진입.
//
// 가로 스크롤 칩 한 줄이 "이걸로 뭘 하라는 건지" 안 보이던 문제를 그리드 랜딩으로 해소.

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
  Scissors,
  Smile,
  Sparkles,
  Stethoscope,
  Syringe,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { Specialty } from "@/types/domain";

type IconType = ComponentType<{ className?: string }>;

// 표준 진료과목 → 아이콘. 없는 과목은 Stethoscope 기본값.
const SPECIALTY_ICON: Record<string, IconType> = {
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
  기타: LayoutGrid,
};

interface CategoryGridProps {
  specialties: Specialty[];
  totalHospitals: number;
  onSelect: (specialty: string) => void; // "" = 전체 병원
  isLoading?: boolean;
}

export function CategoryGrid({
  specialties,
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

      {specialties.map((sp, i) => (
        <Tile
          key={sp.specialty}
          index={i + 1}
          icon={SPECIALTY_ICON[sp.specialty] ?? Stethoscope}
          label={sp.specialty}
          count={sp.count}
          onClick={() => onSelect(sp.specialty)}
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
}

function Tile({ index, icon: Icon, label, count, onClick, primary }: TileProps) {
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
      )}
    >
      <span
        className={cn(
          "flex h-11 w-11 items-center justify-center rounded-full transition-colors",
          primary
            ? "bg-primary/15 text-primary"
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
