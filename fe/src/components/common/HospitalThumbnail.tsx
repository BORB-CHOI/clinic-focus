import { useState } from "react";
import { ImageOff } from "lucide-react";

import { cn } from "@/lib/utils";

interface HospitalThumbnailProps {
  /** 이미지 URL. null/빈 문자열이면 플레이스홀더 */
  src: string | null | undefined;
  /** 병원명 — alt 텍스트 */
  name: string;
  /** 컨테이너 모양 */
  shape?: "square" | "rounded" | "circle";
  /** 외부 클래스 (사이즈 포함) — 미지정 시 부모 사이즈 채움 */
  className?: string;
}

// 병원 대표 이미지 + 폴백 플레이스홀더
//
// src 가 있으면 이미지를, 없거나 로드 실패면 **중립 회색 그라데이션 + '이미지 없음'
// 아이콘**으로 자리를 채운다. (옛 알록달록 hue 배경 + 이니셜 글자는 제거 — 사용자 피드백:
// 알록달록·글자 대신 회색 흐릿 그라데이션 + 병원 이미지 없음 아이콘.)
export function HospitalThumbnail({
  src,
  name,
  shape = "rounded",
  className,
}: HospitalThumbnailProps) {
  const [errored, setErrored] = useState(false);
  const showImage = src && !errored;

  const shapeClass =
    shape === "circle"
      ? "rounded-full"
      : shape === "square"
        ? "rounded-none"
        : "rounded-md";

  return (
    <div
      aria-hidden={!showImage}
      role={showImage ? undefined : "img"}
      aria-label={showImage ? undefined : `${name} 대표 이미지 없음`}
      className={cn(
        "relative shrink-0 overflow-hidden bg-muted",
        shapeClass,
        className,
      )}
    >
      {showImage ? (
        <img
          src={src!}
          alt={`${name} 대표 이미지`}
          loading="lazy"
          onError={() => setErrored(true)}
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="grid h-full w-full place-items-center bg-gradient-to-br from-slate-100 to-slate-200/70">
          <ImageOff
            className="h-[34%] max-h-12 w-[34%] max-w-12 text-slate-400/70"
            strokeWidth={1.5}
            aria-hidden
          />
        </div>
      )}
    </div>
  );
}
