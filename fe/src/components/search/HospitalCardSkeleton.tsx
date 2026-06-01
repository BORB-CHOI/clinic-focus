// HospitalCard 의 새 위계(썸네일 + 태그→이름·신뢰도→메타→한 줄 요약)에 맞춰
// 스켈레톤도 자리 잡아둔다. 본(bone)들은 shimmer(흐르는 하이라이트)로 로딩감.
export function HospitalCardSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-4 text-[0.8em] shadow-sm">
      <div className="flex gap-3">
        {/* 썸네일 */}
        <div className="shimmer h-20 w-20 shrink-0 rounded-md bg-muted" />

        <div className="flex-1 space-y-2">
          {/* 태그 */}
          <div className="flex gap-1.5">
            <div className="shimmer h-5 w-12 rounded-full bg-muted" />
            <div className="shimmer h-5 w-20 rounded-full bg-muted" />
          </div>

          {/* 이름 + 신뢰도 */}
          <div className="flex items-start justify-between gap-3">
            <div className="shimmer h-5 w-2/5 rounded bg-muted" />
            <div className="shimmer h-5 w-16 rounded-full bg-muted" />
          </div>

          {/* 메타 */}
          <div className="shimmer h-3 w-1/3 rounded bg-muted" />
        </div>
      </div>

      {/* 한 줄 요약 */}
      <div className="mt-3 space-y-1.5 border-l-2 border-muted pl-3">
        <div className="shimmer h-3 w-full rounded bg-muted" />
        <div className="shimmer h-3 w-3/4 rounded bg-muted" />
      </div>
    </div>
  );
}
