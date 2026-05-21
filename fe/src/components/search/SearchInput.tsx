import { useEffect, useState, type FormEvent } from "react";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SearchInputProps {
  /** 디바운스가 끝났을 때 + onSubmit 양쪽에서 호출됨 */
  onSearch: (query: string) => void;
  initialValue?: string;
  placeholder?: string;
  /** 디바운스 ms (기본 300) */
  debounceMs?: number;
  className?: string;
}

// 자연어 q 입력. 검색 트리거는 두 갈래:
//  1) onChange 디바운스 (즉시 반응성, 5단계 BE 연동 시 그대로 useQuery key 변동)
//  2) onSubmit (Enter / 버튼) — 디바운스 무시하고 즉시 적용
export function SearchInput({
  onSearch,
  initialValue = "",
  placeholder = "예: M자 탈모 처방받을 수 있는 동네 의원",
  debounceMs = 300,
  className,
}: SearchInputProps) {
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    const id = window.setTimeout(() => {
      onSearch(value.trim());
    }, debounceMs);
    return () => window.clearTimeout(id);
    // onSearch 참조가 바뀌어도 디바운스 재실행할 필요 없음 — value만 트리거
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, debounceMs]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSearch(value.trim());
  };

  return (
    <form
      role="search"
      onSubmit={handleSubmit}
      className={cn("flex items-center gap-2", className)}
    >
      <div className="relative flex-1">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden
        />
        <input
          type="search"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={placeholder}
          aria-label="병원 자연어 검색"
          className="h-10 w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
      </div>
      <Button type="submit" size="default">
        검색
      </Button>
    </form>
  );
}
