// L2 세부 시술·증상 칩 바 — 카테고리 목록 상단에 표시.
//
// 선택된 L1 카테고리 노드의 sub 배열에서 칩을 생성한다.
// "전체" 칩을 맨 앞에 고정하고, sub 라벨은 BE 반환 순서(count 내림차순) 그대로.
// 칩 클릭: focus 설정 / 이미 선택된 칩 재클릭: focus 해제(= "전체"로 복귀).

import { cn } from "@/lib/utils";
import type { CategorySubItem } from "@/types/domain";

interface FocusChipBarProps {
  subItems: CategorySubItem[];
  activeFocus: string;              // "" = 전체(focus 없음)
  onFocusChange: (focus: string) => void; // "" 전달 = 해제
}

export function FocusChipBar({ subItems, activeFocus, onFocusChange }: FocusChipBarProps) {
  if (subItems.length === 0) return null;

  const handleClick = (label: string) => {
    // 이미 선택된 칩을 다시 누르면 해제
    onFocusChange(activeFocus === label ? "" : label);
  };

  return (
    <div
      className="flex gap-2 overflow-x-auto pb-1 scrollbar-none"
      role="group"
      aria-label="세부 시술·증상 필터"
    >
      {/* 전체 칩 */}
      <Chip
        label="전체"
        count={null}
        active={activeFocus === ""}
        onClick={() => onFocusChange("")}
      />

      {subItems.map((item) => (
        <Chip
          key={item.label}
          label={item.label}
          count={item.count}
          active={activeFocus === item.label}
          onClick={() => handleClick(item.label)}
        />
      ))}
    </div>
  );
}

interface ChipProps {
  label: string;
  count: number | null;
  active: boolean;
  onClick: () => void;
}

function Chip({ label, count, active, onClick }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium",
        "transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card text-foreground hover:border-primary/50 hover:bg-accent",
      )}
      aria-pressed={active}
    >
      {label}
      {count !== null && (
        <span
          className={cn(
            "tabular-nums",
            active ? "text-primary-foreground/80" : "text-muted-foreground",
          )}
        >
          {count.toLocaleString()}
        </span>
      )}
    </button>
  );
}
