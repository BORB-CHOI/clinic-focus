import { useEffect, useState, type FormEvent } from "react";
import { Locate, MapPin } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useLocationStore } from "@/lib/locationContext";
import { HAS_KAKAO_MAP_KEY } from "@/lib/env";
import { cn } from "@/lib/utils";

// 헤더에 들어가는 위치 검색 툴바.
//
// 기존에 MapPage 내부에 있던 "위치 이동 / 내 위치" 폼을 전역 위치 상태
// (LocationContext)로 끌어올려 헤더 우측 "내 정보" 옆에 배치. 검색·GPS 결과는
// MapPage 지도 중심으로 공유된다. 카카오 키 없으면 렌더 자체를 생략.
export function LocationSearchBar({ className }: { className?: string }) {
  const { label, searchByName, useMyLocation, searching, error } =
    useLocationStore();
  const [input, setInput] = useState("");

  // 검색이 성공해 label 이 갱신되면 입력칸에 정식 장소명을 반영
  useEffect(() => {
    if (label) setInput(label);
  }, [label]);

  if (!HAS_KAKAO_MAP_KEY) return null;

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    searchByName(input);
  };

  return (
    <div className={cn("flex flex-col items-stretch", className)}>
      <form onSubmit={handleSubmit} className="flex items-center gap-1.5">
        <div className="relative">
          <MapPin
            className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="내 위치 (예: 홍대입구역)"
            aria-label="지도 위치 검색"
            className="h-8 w-20 rounded-full border border-input bg-background py-1 pl-7 pr-3 text-xs placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:w-28 lg:w-44"
          />
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={useMyLocation}
          aria-label="내 위치로 이동"
          className="h-8 shrink-0 px-2"
        >
          <Locate className="h-3.5 w-3.5" aria-hidden />
        </Button>
      </form>
      {searching ? (
        <p className="mt-0.5 px-2 text-[10px] text-muted-foreground">검색 중…</p>
      ) : error ? (
        <p className="mt-0.5 px-2 text-[10px] text-destructive">{error}</p>
      ) : null}
    </div>
  );
}
