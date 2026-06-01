// 페이지네이션 UI — 이전/다음 버튼 + 현재 페이지/전체 페이지 표시.
// meta.total 기준으로 totalPages 계산. 1 페이지일 때는 렌더하지 않는다.

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PaginationProps {
  page: number;      // 현재 페이지 (1-base)
  total: number;     // 전체 결과 수
  pageSize: number;  // 페이지당 건수
  onPage: (page: number) => void;
}

export function Pagination({ page, total, pageSize, onPage }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (totalPages <= 1) return null;

  return (
    <nav
      role="navigation"
      aria-label="검색 결과 페이지 탐색"
      className="flex items-center justify-center gap-3 py-4"
    >
      <Button
        variant="outline"
        size="sm"
        onClick={() => onPage(page - 1)}
        disabled={page <= 1}
        aria-label="이전 페이지"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden />
        이전
      </Button>

      <span className="text-sm text-muted-foreground">
        <span className="font-semibold text-foreground">{page}</span>
        {" / "}
        {totalPages}
      </span>

      <Button
        variant="outline"
        size="sm"
        onClick={() => onPage(page + 1)}
        disabled={page >= totalPages}
        aria-label="다음 페이지"
      >
        다음
        <ChevronRight className="h-4 w-4" aria-hidden />
      </Button>
    </nav>
  );
}
