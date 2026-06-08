// 검색 이벤트 로깅 — 데이터 해자 핵심
//
// 두 개의 이벤트 경로가 병렬로 동작한다:
//   [기존] POST /api/events        → Main 테이블 (impression/click/select 단순 기록)
//   [신규] POST /api/analytics/events → Analytics 테이블 (환경 컨텍스트 + 병원 컨텍스트 포함)
//
// Analytics 이벤트는 FE가 이미 알고 있는 병원 정보(specialty·sigungu)를 함께 전송해
// BE가 Main 테이블을 전혀 조회하지 않아도 된다. 완전 독립.
//
// 두 경로 모두 fire-and-forget — 실패해도 UX 차단 금지.

import { getDeviceId } from "./device";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type EventType = "impression" | "click" | "select";

// ── 기존 이벤트 (Main 테이블) ───────────────────────────────────────────────

interface EventPayload {
  event_type: EventType;
  session_id: string;
  hospital_id: string;
  query?: string;
  position?: number;
}

function postEvent(payload: EventPayload): void {
  fetch(`${API_BASE}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => {});
}

export function trackImpression(hospitalId: string, query?: string, position?: number): void {
  postEvent({ event_type: "impression", session_id: getDeviceId(), hospital_id: hospitalId, query, position });
}

export function trackClick(hospitalId: string, query?: string, position?: number): void {
  postEvent({ event_type: "click", session_id: getDeviceId(), hospital_id: hospitalId, query, position });
}

export function trackSelect(hospitalId: string, query?: string): void {
  postEvent({ event_type: "select", session_id: getDeviceId(), hospital_id: hospitalId, query });
}

// ── Analytics 이벤트 (Analytics 테이블 전용) ────────────────────────────────

export interface AnalyticsHospitalCtx {
  hospitalId: string;
  hospitalName: string;
  standardSpecialty: string;
  sigungu: string;
}

interface AnalyticsPayload {
  event_type: EventType;
  device_id: string;
  hospital_id: string;
  hospital_name: string;
  standard_specialty: string;
  sigungu: string;
  query?: string;
  position?: number;
  lat?: number;
  lng?: number;
}

function postAnalyticsEvent(payload: AnalyticsPayload): void {
  fetch(`${API_BASE}/api/analytics/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => {});
}

/** 클릭 이벤트 — 병원 컨텍스트 + 위치(날씨 조회용) 포함 */
export function trackAnalyticsClick(
  ctx: AnalyticsHospitalCtx,
  opts?: { query?: string; position?: number; lat?: number; lng?: number },
): void {
  postAnalyticsEvent({
    event_type:        "click",
    device_id:         getDeviceId(),
    hospital_id:       ctx.hospitalId,
    hospital_name:     ctx.hospitalName,
    standard_specialty: ctx.standardSpecialty,
    sigungu:           ctx.sigungu,
    query:             opts?.query,
    position:          opts?.position,
    lat:               opts?.lat,
    lng:               opts?.lng,
  });
}

/** 노출 이벤트 */
export function trackAnalyticsImpression(
  ctx: AnalyticsHospitalCtx,
  opts?: { query?: string; position?: number },
): void {
  postAnalyticsEvent({
    event_type:        "impression",
    device_id:         getDeviceId(),
    hospital_id:       ctx.hospitalId,
    hospital_name:     ctx.hospitalName,
    standard_specialty: ctx.standardSpecialty,
    sigungu:           ctx.sigungu,
    query:             opts?.query,
    position:          opts?.position,
  });
}

/** 선택 이벤트 (길 안내 등 전환) */
export function trackAnalyticsSelect(
  ctx: AnalyticsHospitalCtx,
  opts?: { query?: string; lat?: number; lng?: number },
): void {
  postAnalyticsEvent({
    event_type:        "select",
    device_id:         getDeviceId(),
    hospital_id:       ctx.hospitalId,
    hospital_name:     ctx.hospitalName,
    standard_specialty: ctx.standardSpecialty,
    sigungu:           ctx.sigungu,
    query:             opts?.query,
    lat:               opts?.lat,
    lng:               opts?.lng,
  });
}

// ── 광고 이벤트 ─────────────────────────────────────────────────────────────
// 광고(협찬) 슬롯 클릭 기록. BE 광고 엔드포인트 부재 단계라 fire-and-forget 로
// /api/events 에 ad_click 으로 흘려보낸다 (서버가 무시해도 UX 영향 없음).

export function trackAdClick(adId: string, hospitalId: string | null): void {
  fetch(`${API_BASE}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_type: "ad_click",
      session_id: getDeviceId(),
      ad_id: adId,
      hospital_id: hospitalId ?? undefined,
    }),
  }).catch(() => {});
}
