import { MapPin, Phone, ExternalLink, Calendar, Clock, Navigation } from "lucide-react";
import { trackAnalyticsSelect, trackAnalyticsClick } from "@/lib/events";

import { Section } from "@/components/common/Section";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type {
  AppointmentMethod,
  Contact,
  DayHours,
  Location,
  OperatingHours,
} from "@/types/domain";

const APPT_LABEL: Record<AppointmentMethod, string> = {
  walk_in: "방문",
  phone: "전화",
  online: "온라인",
};

interface BasicInfoSectionProps {
  hospitalId: string;
  hospitalName: string;
  standardSpecialty: string;
  location: Location;
  operating_hours: OperatingHours | null;
  contact: Contact;
}

function formatHours(h: DayHours | null): string {
  if (!h) return "휴진";
  const lunch =
    h.lunch_start && h.lunch_end
      ? ` (점심 ${h.lunch_start}~${h.lunch_end})`
      : "";
  return `${h.open}~${h.close}${lunch}`;
}

// 현재 영업 상태 — 데모 시연 시점 기준 빠르게 보여주기 위한 간이 판정.
// 시연용이라 점심시간·공휴일 같은 디테일은 다음 라운드로 미룸.
function isOpenNow(hours: OperatingHours, now = new Date()): boolean {
  const day = now.getDay(); // 0=일, 6=토
  const slot =
    day === 0 ? hours.sunday : day === 6 ? hours.saturday : hours.weekday;
  if (!slot) return false;
  const cur = now.getHours() * 60 + now.getMinutes();
  const [oh, om] = slot.open.split(":").map(Number);
  const [ch, cm] = slot.close.split(":").map(Number);
  const open = oh * 60 + om;
  const close = ch * 60 + cm;
  return cur >= open && cur < close;
}

// ⑤ 기본 운영 정보 — 위치·운영시간·연락처
//
// 굿닥/모두닥 상세 페이지에서 가장 액션에 직결되는 영역이라 시각 위계를 다음처럼 정돈:
//   - 헤더 액션 슬롯에 "현재 영업 중/마감" 배지
//   - 핵심 행동(전화·홈페이지)을 큰 버튼 형태로 상단에
//   - 주소·운영시간·예약 방법은 라벨 아이콘으로 위계 표시
export function BasicInfoSection({
  hospitalId,
  hospitalName,
  standardSpecialty,
  location,
  operating_hours,
  contact,
}: BasicInfoSectionProps) {
  const openNow = operating_hours ? isOpenNow(operating_hours) : false;
  const ctx = { hospitalId, hospitalName, standardSpecialty, sigungu: location.sigungu };

  return (
    <Section
      id="section-basic-info"
      title="운영 정보"
      badge="⑤"
      subtitle="위치, 운영시간, 연락처"
      action={
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
      }
    >
      {/* 핵심 액션: 전화 + 길 안내 + 홈페이지 */}
      <div className="grid gap-2 sm:grid-cols-2">
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
        {contact.homepage_url ? (
          <a
            href={contact.homepage_url}
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

      {/* 운영시간 */}
      <InfoRow icon={<Clock className="h-4 w-4" />} label="운영시간">
        {operating_hours ? (
          <>
            <ul className="space-y-1">
              <HoursRow label="평일" hours={operating_hours.weekday} />
              <HoursRow label="토요일" hours={operating_hours.saturday} />
              <HoursRow label="일요일" hours={operating_hours.sunday} />
            </ul>
            {(operating_hours.night_clinic || operating_hours.holiday_clinic) ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {operating_hours.night_clinic ? (
                  <Badge variant="secondary" className="font-normal">
                    야간 진료
                  </Badge>
                ) : null}
                {operating_hours.holiday_clinic ? (
                  <Badge variant="secondary" className="font-normal">
                    공휴일 진료
                  </Badge>
                ) : null}
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">운영시간 정보 없음</p>
        )}
      </InfoRow>

      <Separator className="my-5" />

      {/* 예약·주차 */}
      <InfoRow icon={<Calendar className="h-4 w-4" />} label="예약·주차">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">예약</span>
          {contact.appointment_methods.length > 0 ? (
            contact.appointment_methods.map((m) => (
              <Badge key={m} variant="outline" className="font-normal">
                {APPT_LABEL[m]}
              </Badge>
            ))
          ) : (
            <span className="text-xs text-muted-foreground">정보 없음</span>
          )}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          주차 {contact.parking_available ? "가능" : "불가"}
        </p>
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

function HoursRow({ label, hours }: { label: string; hours: DayHours | null }) {
  const closed = !hours;
  return (
    <li className="flex items-baseline justify-between gap-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn("font-mono", closed && "text-muted-foreground")}>
        {formatHours(hours)}
      </span>
    </li>
  );
}
