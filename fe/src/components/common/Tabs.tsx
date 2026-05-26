import { useSearchParams } from "react-router-dom";

import { cn } from "@/lib/utils";

interface TabItem<T extends string> {
  value: T;
  label: string;
  /** 라벨 옆 작은 카운트·뱃지 */
  hint?: React.ReactNode;
}

interface TabsProps<T extends string> {
  /** URL 쿼리 파라미터 키 (기본 "tab") */
  paramKey?: string;
  /** 쿼리에 값이 없을 때 사용할 기본 탭 */
  defaultValue: T;
  items: readonly TabItem<T>[];
  /** 각 탭 내용 — value 키로 매핑 */
  children: Record<T, React.ReactNode>;
  /** sticky 로 띄울지 여부 (기본 true) */
  sticky?: boolean;
  className?: string;
}

// URL 쿼리스트링과 동기화되는 탭 컨테이너.
//
// shadcn/ui Tabs 를 직접 들이지 않고 동일 패턴(role="tablist"/"tab"/"tabpanel")만
// 손으로 짠다. 본 PoC 가 의존하는 탭 기능은 단일 그룹·키보드 네비게이션 정도라
// 의존성 추가보다 직접 구현이 비용 ↓.
//
// 새로고침·뒤로가기·공유에서 활성 탭 보존 → 셸의 URL 동기화 방향과 일관.
export function Tabs<T extends string>({
  paramKey = "tab",
  defaultValue,
  items,
  children,
  sticky = true,
  className,
}: TabsProps<T>) {
  const [searchParams, setSearchParams] = useSearchParams();
  const raw = searchParams.get(paramKey);
  const active = (items.find((i) => i.value === raw)?.value ?? defaultValue) as T;

  const handleSelect = (value: T) => {
    const next = new URLSearchParams(searchParams);
    if (value === defaultValue) next.delete(paramKey);
    else next.set(paramKey, value);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className={className}>
      <div
        role="tablist"
        aria-label="병원 상세 정보 탭"
        className={cn(
          "flex gap-1 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75",
          sticky && "sticky top-[6.5rem] z-10",
        )}
      >
        {items.map((item) => {
          const isActive = item.value === active;
          return (
            <button
              key={item.value}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${item.value}`}
              id={`tab-${item.value}`}
              onClick={() => handleSelect(item.value)}
              className={cn(
                "relative flex items-center gap-1.5 px-4 py-3 text-sm font-medium transition-colors",
                isActive
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <span>{item.label}</span>
              {item.hint ? (
                <span className="text-xs text-muted-foreground">
                  {item.hint}
                </span>
              ) : null}
              {/* 활성 탭 하단 보더 */}
              <span
                aria-hidden
                className={cn(
                  "absolute inset-x-2 -bottom-px h-0.5 rounded-full transition-colors",
                  isActive ? "bg-primary" : "bg-transparent",
                )}
              />
            </button>
          );
        })}
      </div>

      {items.map((item) => (
        <div
          key={item.value}
          role="tabpanel"
          id={`tabpanel-${item.value}`}
          aria-labelledby={`tab-${item.value}`}
          hidden={item.value !== active}
          className="pt-4"
        >
          {item.value === active ? children[item.value] : null}
        </div>
      ))}
    </div>
  );
}
