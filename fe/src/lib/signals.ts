import type { SignalKey } from "@/types/domain";

// 시그널 키 → UI 라벨. fe/CLAUDE.md 명시:
// citations 배지 예시 [사이트] [Vision] [블로그] [후기]
export const SIGNAL_LABEL: Record<SignalKey, string> = {
  self_claim: "사이트",
  vision: "Vision",
  blog: "블로그",
  reviews: "후기",
  public_data: "공공데이터",
};

// detailed_signals 영역의 키 (citations에는 있지만 detailed_signals엔 없는 키 제외)
export type DetailedSignalKey = Exclude<SignalKey, "public_data">;

export function detailedSignalAnchorId(key: DetailedSignalKey): string {
  return `signal-${key}`;
}
