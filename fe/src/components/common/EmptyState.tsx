import { cn } from "@/lib/utils";

interface EmptyStateProps {
  message?: string;
  className?: string;
}

// data_completeness < 0.6 또는 영역 데이터가 비어있을 때
export function EmptyState({
  message = "정보 부족",
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "rounded-md border border-dashed bg-muted/40 px-4 py-6 text-center text-sm text-muted-foreground",
        className,
      )}
    >
      {message}
    </div>
  );
}
