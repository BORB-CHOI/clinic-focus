import { Link, useLocation } from "react-router-dom";
import { List, Map } from "lucide-react";

import { cn } from "@/lib/utils";

// /search ↔ /map 토글. 굿닥의 하단 탭바 역할을 데스크톱에선 검색바 아래
// 세그먼티드 컨트롤로 옮겼다. 검색어(?q=)는 라우트 갈아탈 때 보존.
export function ViewModeToggle({ className }: { className?: string }) {
  const location = useLocation();
  const search = location.search; // ?q=... 보존
  const onSearch = location.pathname.startsWith("/search");
  const onMap = location.pathname.startsWith("/map");

  return (
    <nav
      aria-label="검색 보기 전환"
      className={cn(
        "inline-flex items-center gap-1 rounded-full border bg-card p-1 text-sm",
        className,
      )}
    >
      <ToggleLink to={`/search${search}`} active={onSearch} icon={<List />}>
        리스트
      </ToggleLink>
      <ToggleLink to={`/map${search}`} active={onMap} icon={<Map />}>
        지도
      </ToggleLink>
    </nav>
  );
}

function ToggleLink({
  to,
  active,
  icon,
  children,
}: {
  to: string;
  active: boolean;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      to={to}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-1.5 rounded-full px-3 py-1 transition-colors",
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
      <span aria-hidden className="[&>svg]:h-4 [&>svg]:w-4">
        {icon}
      </span>
      <span>{children}</span>
    </Link>
  );
}
