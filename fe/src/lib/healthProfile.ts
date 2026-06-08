// 건강 프로파일 — 익명 신체 정보 관리
//
// 키·몸무게는 이 파일 안에서만 계산되고 즉시 버킷으로 변환.
// 서버에는 버킷값(예: "normal")만 전달 — 원본 수치는 외부로 나가지 않는다.

import { getDeviceId } from "./device";

const STORAGE_KEY = "app_health_profile";
const API_BASE    = (import.meta.env.VITE_API_BASE_URL ?? "") as string;

// ── 타입 ──────────────────────────────────────────────────────────────────

export type GenderBucket = "male" | "female" | "other" | "unknown";
export type AgeBucket    = "teens" | "20s" | "30s" | "40s" | "50plus" | "unknown";
export type BmiBucket    = "underweight" | "normal" | "overweight" | "obese" | "unknown";

export interface HealthProfile {
  genderBucket: GenderBucket;
  ageBucket:    AgeBucket;
  bmiBucket:    BmiBucket;
}

// ── BMI 계산 (FE 전용 — 서버 미전송) ─────────────────────────────────────

export function calcBmiBucket(heightCm: number, weightKg: number): BmiBucket {
  if (!heightCm || !weightKg || heightCm < 50 || weightKg < 10) return "unknown";
  const bmi = weightKg / (heightCm / 100) ** 2;
  if (bmi < 18.5) return "underweight";
  if (bmi < 25)   return "normal";
  if (bmi < 30)   return "overweight";
  return "obese";
}

// ── localStorage 읽기/쓰기 ─────────────────────────────────────────────────

export function getHealthProfile(): HealthProfile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as HealthProfile;
  } catch {}
  return { genderBucket: "unknown", ageBucket: "unknown", bmiBucket: "unknown" };
}

export function hasHealthProfile(): boolean {
  const p = getHealthProfile();
  return p.genderBucket !== "unknown" || p.ageBucket !== "unknown";
}

export function clearHealthProfile(): void {
  localStorage.removeItem(STORAGE_KEY);
}

// ── 저장 + BE 전송 ────────────────────────────────────────────────────────

export async function saveHealthProfile(profile: HealthProfile): Promise<void> {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));

  // BE에는 버킷값만 전송 (fire-and-forget)
  fetch(`${API_BASE}/api/analytics/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      device_id:     getDeviceId(),
      gender_bucket: profile.genderBucket,
      age_bucket:    profile.ageBucket,
      bmi_bucket:    profile.bmiBucket,
    }),
  }).catch(() => {});
}
