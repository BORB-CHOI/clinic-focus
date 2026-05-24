// HospitalCard 의 새 위계(썸네일 + 태그→이름·신뢰도→메타→한 줄 요약)에 맞춰
// 스켈레톤도 자리 잡아둔다. 5단계 BE 연동 시 useQuery 로딩 단계에 노출.
export function HospitalCardSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-4 text-[0.8em] shadow-sm">
      <div className="flex gap-3">
        {/* 썸네일 */}
        <div className="h-20 w-20 shrink-0 animate-pulse rounded-md bg-muted" />

        <div className="flex-1 space-y-2">
          {/* 태그 */}
          <div className="flex gap-1.5">
            <div className="h-5 w-12 animate-pulse rounded-full bg-muted" />
            <div className="h-5 w-20 animate-pulse rounded-full bg-muted" />
          </div>

          {/* 이름 + 신뢰도 */}
          <div className="flex items-start justify-between gap-3">
            <div className="h-5 w-2/5 animate-pulse rounded bg-muted" />
            <div className="h-5 w-16 animate-pulse rounded-full bg-muted" />
          </div>

          {/* 메타 */}
          <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
        </div>
      </div>

      {/* 한 줄 요약 */}
      <div className="mt-3 space-y-1.5 border-l-2 border-muted pl-3">
        <div className="h-3 w-full animate-pulse rounded bg-muted" />
        <div className="h-3 w-3/4 animate-pulse rounded bg-muted" />
      </div>
    </div>
  );
}
