import { MapPin, Phone, ExternalLink, Clock, Navigation, ParkingCircle } from "lucide-react";
import { trackAnalyticsSelect, trackAnalyticsClick } from "@/lib/events";

import { Section } from "@/components/common/Section";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type {
  Contact,
  Location,
  OperatingHours,
} from "@/types/domain";

// ── 영업 중 판정 ──────────────────────────────────────────────────────────
// 평문 string "HH:MM~HH:MM" 파싱. 점심 시간 고려하지 않는 간이 판정 (데모용).
function parseTimeRange(s: string): [number, number] | null {
  // 예: "09:30~18:00", "09:00~17:30"
  const m = s.match(/^(\d{1,2}):(\d{2})[~\-](\d{1,2}):(\d{2})/);
  if (!m) return null;
  const open = parseInt(m[1]) * 60 + parseInt(m[2]);
  const close = parseInt(m[3]) * 60 + parseInt(m[4]);
  return [open, close];
}

function isOpenNow(hours: OperatingHours, now = new Date()): boolean {
  const day = now.getDay(); // 0=일, 6=토
  const raw =
    day === 0 ? hours.sunday : day === 6 ? hours.saturday : hours.weekday;
  if (!raw) return false;
  // "휴진" 같은 텍스트는 시간 파싱 실패 → false
  const range = parseTimeRange(raw);
  if (!range) return false;
  const cur = now.getHours() * 60 + now.getMinutes();
  return cur >= range[0] && cur < range[1];
}

// ── 요일별 텍스트 → 표시용 (휴진 여부 스타일 분기) ──────────────────────
function isDayOff(val: string | null): boolean {
  if (!val) return true;
  return /휴진|휴무|없음|미운영/.test(val);
}

// ⑤ 기본 운영 정보 — 위치·운영시간·연락처
//
// 출처: 심평원 신고 기준(OperatingHours, HospitalMeta.contact)
// 영업 중 배지 — 평문 string 시간 범위 간이 파싱(데모용, 점심시간·공휴일 미반영)
export function BasicInfoSection({
  hospitalId,
  hospitalName,
  standardSpecialty,
  location,
  operating_hours,
  contact,
}: {
  hospitalId: string;
  hospitalName: string;
  standardSpecialty: string;
  location: Location;
  operating_hours: OperatingHours | null;
  contact: Contact;
}) {
  const openNow = operating_hours ? isOpenNow(operating_hours) : false;
  const ctx = { hospitalId, hospitalName, standardSpecialty, sigungu: location.sigungu };

  // 운영시간 필드 중 하나라도 값이 있으면 영역 표시
  const hasHoursData =
    operating_hours !== null &&
    (
      operating_hours.weekday !== null ||
      operating_hours.saturday !== null ||
      operating_hours.sunday !== null ||
      operating_hours.holiday !== null ||
      operating_hours.lunch_break !== null ||
      operating_hours.parking_note !== null
    );

  return (
    <Section
      id="section-basic-info"
      title="운영 정보"
      badge="⑤"
      subtitle="위치, 운영시간, 연락처"
      action={
        operating_hours ? (
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
              openNow
                ? "border-confidence-high-100 bg-confidence-high-50 text-confidence-high-700"
                : "border-confidence-low-100 bg-confidence-low-50 text-confidence-low-700",
            )}
          >
            <span
              aria-hidden
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                openNow ? "bg-confidence-high-500" : "bg-confidence-low-500",
              )}
            />
            {openNow ? "현재 영업 중" : "마감"}
          </span>
        ) : null
      }
    >
      {/* 핵심 액션: 전화 + 길 안내 + 홈페이지 */}
      <div className="grid gap-2 sm:grid-cols-2">
        {contact.phone ? (
          <a
            href={`tel:${contact.phone}`}
            onClick={() => trackAnalyticsSelect(ctx, { lat: location.lat, lng: location.lng })}
            className="group flex items-center justify-between gap-3 rounded-md border border-primary/20 bg-primary/5 px-3 py-2.5 text-sm transition-colors hover:border-primary hover:bg-primary/10"
          >
            <span className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-primary" aria-hidden />
              <span className="font-medium">전화하기</span>
            </span>
            <span className="font-mono text-xs text-muted-foreground group-hover:text-foreground">
              {contact.phone}
            </span>
          </a>
        ) : null}
        {location.lat && location.lng ? (
          <a
            href={`https://map.kakao.com/link/to/${encodeURIComponent(hospitalName)},${location.lat},${location.lng}`}
            target="_blank"
            rel="noreferrer"
            onClick={() => trackAnalyticsSelect(ctx, { lat: location.lat, lng: location.lng })}
            className="group flex items-center justify-between gap-3 rounded-md border bg-background px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-accent"
          >
            <span className="flex items-center gap-2">
              <Navigation className="h-4 w-4 text-muted-foreground group-hover:text-primary" aria-hidden />
              <span className="font-medium">길 안내</span>
            </span>
            <span className="text-xs text-muted-foreground">↗</span>
          </a>
        ) : null}
        {contact.website_url ? (
          <a
            href={contact.website_url}
            target="_blank"
            rel="noreferrer"
            onClick={() => trackAnalyticsClick(ctx, { lat: location.lat, lng: location.lng })}
            className="group flex items-center justify-between gap-3 rounded-md border bg-background px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-accent"
          >
            <span className="flex items-center gap-2">
              <ExternalLink className="h-4 w-4 text-muted-foreground group-hover:text-primary" aria-hidden />
              <span className="font-medium">홈페이지</span>
            </span>
            <span className="text-xs text-muted-foreground">↗</span>
          </a>
        ) : null}
        {contact.reservation_url ? (
          <a
            href={contact.reservation_url}
            target="_blank"
            rel="noreferrer"
            onClick={() => trackAnalyticsClick(ctx, { lat: location.lat, lng: location.lng })}
            className="group flex items-center justify-between gap-3 rounded-md border bg-background px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-accent"
          >
            <span className="flex items-center gap-2">
              <ExternalLink className="h-4 w-4 text-muted-foreground group-hover:text-primary" aria-hidden />
              <span className="font-medium">온라인 예약</span>
            </span>
            <span className="text-xs text-muted-foreground">↗</span>
          </a>
        ) : null}
      </div>

      <Separator className="my-5" />

      {/* 주소 */}
      <InfoRow icon={<MapPin className="h-4 w-4" />} label="주소">
        <p>{location.address}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {location.sido} {location.sigungu}
          {location.dong ? ` ${location.dong}` : ""}
        </p>
      </InfoRow>

      <Separator className="my-5" />

      {/* 운영시간 — 심평원 신고 기준 */}
      <InfoRow icon={<Clock className="h-4 w-4" />} label="운영시간">
        {hasHoursData ? (
          <>
            {/* 출처 배지 — 주체 명시 원칙 */}
            <p className="mb-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="mr-1 px-1.5 py-0 text-[10px] font-normal">
                심평원 신고 기준
              </Badge>
              이 병원이 심평원에 신고한 운영 정보입니다
            </p>
            <ul className="space-y-1">
              {operating_hours!.weekday !== null ? (
                <HoursRow label="평일" value={operating_hours!.weekday} />
              ) : null}
              {operating_hours!.saturday !== null ? (
                <HoursRow label="토요일" value={operating_hours!.saturday} />
              ) : null}
              {operating_hours!.sunday !== null ? (
                <HoursRow label="일요일" value={operating_hours!.sunday} />
              ) : null}
              {operating_hours!.holiday !== null ? (
                <HoursRow label="공휴일" value={operating_hours!.holiday} />
              ) : null}
              {operating_hours!.lunch_break !== null ? (
                <HoursRow label="점심시간" value={operating_hours!.lunch_break} />
              ) : null}
            </ul>
            {/* 주차 안내 */}
            {operating_hours!.parking_note ? (
              <div className="mt-3 flex items-start gap-2">
                <ParkingCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
                <span className="text-xs text-muted-foreground">
                  주차 — {operating_hours!.parking_note}
                </span>
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            심평원 신고 운영정보 없음
          </p>
        )}
      </InfoRow>
    </Section>
  );
}

function InfoRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3 text-sm">
      <span
        aria-hidden
        className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-muted text-muted-foreground"
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <div className="mt-1">{children}</div>
      </div>
    </div>
  );
}

/** 요일별 운영시간 1행 — 평문 string 그대로 표시. 휴진 텍스트면 흐리게. */
function HoursRow({ label, value }: { label: string; value: string }) {
  const closed = isDayOff(value);
  return (
    <li className="flex items-baseline justify-between gap-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn("font-mono text-sm", closed && "text-muted-foreground")}>
        {value}
      </span>
    </li>
  );
}
