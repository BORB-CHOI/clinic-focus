import { useState } from "react";

import { cn } from "@/lib/utils";

interface HospitalThumbnailProps {
  /** 이미지 URL. null/빈 문자열이면 플레이스홀더 */
  src: string | null | undefined;
  /** 병원명 — 이니셜 폴백·alt 텍스트 */
  name: string;
  /** 컨테이너 모양 */
  shape?: "square" | "rounded" | "circle";
  /** 외부 클래스 (사이즈 포함) — 미지정 시 부모 사이즈 채움 */
  className?: string;
}

// 병원 대표 이미지 + 폴백 플레이스홀더
//
// BE 측 이미지 수집 로직이 미구현이라 src 는 대부분 null. 이 경우
// 그라데이션 배경 + 병원명 첫 글자 이니셜로 자리를 채워둔다 (의료진
// 아바타 톤과 동일). 이미지 로드 실패도 같은 폴백으로 처리.
//
// hue 는 병원명 hash 로 안정 분포 → 같은 병원이 항상 같은 색.
export function HospitalThumbnail({
  src,
  name,
  shape = "rounded",
  className,
}: HospitalThumbnailProps) {
  const [errored, setErrored] = useState(false);
  const showImage = src && !errored;
  const initial = name.trim().charAt(0) || "?";

  // 이름 hash 로 hue 결정 — 안정적 분포
  const hue = Math.abs(hashCode(name)) % 360;
  const gradient = `linear-gradient(135deg, hsl(${hue} 70% 55%), hsl(${(hue + 35) % 360} 65% 45%))`;

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
      aria-label={showImage ? undefined : `${name} 대표 이미지 자리`}
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
        <div
          className="grid h-full w-full place-items-center text-white"
          style={{ background: gradient }}
        >
          <span className="text-[1.5em] font-semibold drop-shadow-sm">
            {initial}
          </span>
        </div>
      )}
    </div>
  );
}

// djb2 변형 — 결정적 분포만 필요해 충돌 강도는 신경 안 씀
function hashCode(str: string): number {
  let h = 5381;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) + h) ^ str.charCodeAt(i);
  }
  return h;
}
