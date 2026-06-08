import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams, useLocation } from "react-router-dom";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface StickySearchBarProps {
  /** 디바운스 ms (기본 300) */
  debounceMs?: number;
  className?: string;
}

// 글로벌 셸의 sticky 검색바.
//
// 검색어는 URL 쿼리스트링(?q=)에 동기화돼 새로고침·공유·뒤로가기에서 보존된다.
//   /search 페이지: 입력 즉시 q 갱신 (디바운스)
//   /map 페이지: q 변경 시 그대로 /search?q=...&radius_km=... 식의 결합도 가능
//   /hospitals/:id 페이지: 입력 후 Enter 또는 검색 버튼 → /search?q= 로 이동
//
// SearchPage.tsx 의 useSearchParams("q") 가 이 셸과 짝을 이뤄 결과 리스트를
// 갱신한다. (이번 라운드에 SearchPage 도 같이 적응시킨다)
export function StickySearchBar({
  debounceMs = 350,
  className,
}: StickySearchBarProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const isSearchPage = location.pathname.startsWith("/search");
  // 지도 페이지도 검색바 제자리에서 동작 (이탈 금지)
  const isMapPage = location.pathname.startsWith("/map");
  const isInPageSearch = isSearchPage || isMapPage;

  // 입력 컨트롤은 로컬 상태로 두고, /search 에서는 디바운스로 URL 에 반영
  // (다른 페이지에서는 Enter/버튼 클릭 시점에 /search 로 navigate)
  const [value, setValue] = useState(searchParams.get("q") ?? "");
  // 디바운스가 *우리가* URL 에 푸시한 마지막 q. 이걸로 "외부 변경(뒤로가기·링크)"과
  // "내 타이핑이 만든 URL 변경"을 구분 — 후자를 입력에 되돌려쓰면 한글 IME 조합이 깨진다.
  const lastPushed = useRef<string | null>(null);

  // URL→입력 동기화는 *외부* 변경(뒤로가기·외부 링크)일 때만. 내가 방금 푸시한 q 는 skip
  // (안 그러면 타이핑 중 setValue 재실행 → 한글 조합 리셋 → 입력이 지워짐).
  useEffect(() => {
    const urlQ = searchParams.get("q") ?? "";
    if (urlQ !== lastPushed.current) {
      setValue(urlQ);
    }
  }, [searchParams]);

  // /search, /map 에서 디바운스로 URL q 업데이트 (다른 페이지는 navigate 시점에 처리)
  useEffect(() => {
    if (!isInPageSearch) return;
    const id = window.setTimeout(() => {
      const trimmed = value.trim();
      const current = searchParams.get("q") ?? "";
      if (trimmed === current) return;
      lastPushed.current = trimmed; // 내 푸시로 표시 → 위 동기화 effect 가 입력을 안 건드림
      const next = new URLSearchParams(searchParams);
      if (trimmed) next.set("q", trimmed);
      else next.delete("q");
      setSearchParams(next, { replace: true });
    }, debounceMs);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, isInPageSearch, debounceMs]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = value.trim();
    if (isInPageSearch) {
      // /search, /map: URL ?q= 만 갱신, 페이지 이동 없음
      const next = new URLSearchParams(searchParams);
      if (trimmed) next.set("q", trimmed);
      else next.delete("q");
      setSearchParams(next, { replace: false });
    } else {
      // /hospitals/:id 등 그 외 → 검색 페이지로 이동
      const next = new URLSearchParams();
      if (trimmed) next.set("q", trimmed);
      navigate(`/search?${next.toString()}`);
    }
  };

  return (
    <div
      className={cn(
        "sticky top-[6.5rem] z-20 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75",
        className,
      )}
    >
      <div className="container py-2.5">
        <form
          role="search"
          onSubmit={handleSubmit}
          className="flex items-center gap-2"
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
              placeholder="어디가 불편하세요? — 예: M자 탈모 처방받을 수 있는 동네 의원"
              aria-label="병원 자연어 검색"
              className="h-10 w-full rounded-md border border-input bg-background py-2 pl-9 pr-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
          </div>
          <Button type="submit" size="default">
            검색
          </Button>
        </form>
      </div>
    </div>
  );
}
