// 디바운스 트랜지션·BE 연동(5단계) 시 로딩 표시용 단순 스켈레톤
// 지금은 동기 필터링이라 거의 안 보이지만 자리만 잡아둔다
export function HospitalCardSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2">
          <div className="h-4 w-2/5 animate-pulse rounded bg-muted" />
          <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-5 w-14 animate-pulse rounded-full bg-muted" />
      </div>
      <div className="mt-3 space-y-1.5">
        <div className="h-3 w-full animate-pulse rounded bg-muted" />
        <div className="h-3 w-3/4 animate-pulse rounded bg-muted" />
      </div>
      <div className="mt-3 flex gap-1.5">
        <div className="h-5 w-12 animate-pulse rounded-full bg-muted" />
        <div className="h-5 w-20 animate-pulse rounded-full bg-muted" />
      </div>
    </div>
  );
}
