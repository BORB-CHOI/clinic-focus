import { Section } from "@/components/common/Section";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
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
  location: Location;
  operating_hours: OperatingHours;
  contact: Contact;
}

function formatHours(h: DayHours | null): string {
  if (!h) return "휴진";
  const lunch =
    h.lunch_start && h.lunch_end ? ` (점심 ${h.lunch_start}~${h.lunch_end})` : "";
  return `${h.open}~${h.close}${lunch}`;
}

// ⑤ 기본 운영 정보 — 위치·운영시간·연락처
export function BasicInfoSection({
  location,
  operating_hours,
  contact,
}: BasicInfoSectionProps) {
  return (
    <Section
      id="section-basic-info"
      title="운영 정보"
      badge="⑤"
      subtitle="위치, 운영시간, 연락처"
    >
      <div>
        <h3 className="mb-1 text-sm font-semibold text-muted-foreground">
          주소
        </h3>
        <p className="text-sm">{location.address}</p>
        <p className="text-xs text-muted-foreground">
          {location.sido} {location.sigungu}
          {location.dong ? ` ${location.dong}` : ""}
        </p>
      </div>

      <Separator className="my-4" />

      <div>
        <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
          운영시간
        </h3>
        <ul className="space-y-1 text-sm">
          <li className="flex justify-between">
            <span className="text-muted-foreground">평일</span>
            <span>{formatHours(operating_hours.weekday)}</span>
          </li>
          <li className="flex justify-between">
            <span className="text-muted-foreground">토요일</span>
            <span>{formatHours(operating_hours.saturday)}</span>
          </li>
          <li className="flex justify-between">
            <span className="text-muted-foreground">일요일</span>
            <span>{formatHours(operating_hours.sunday)}</span>
          </li>
        </ul>
        <div className="mt-2 flex flex-wrap gap-1">
          {operating_hours.night_clinic ? (
            <Badge variant="secondary">야간 진료</Badge>
          ) : null}
          {operating_hours.holiday_clinic ? (
            <Badge variant="secondary">공휴일 진료</Badge>
          ) : null}
        </div>
      </div>

      <Separator className="my-4" />

      <div>
        <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
          연락처
        </h3>
        <ul className="space-y-1 text-sm">
          <li>
            <a
              href={`tel:${contact.phone}`}
              className="underline-offset-2 hover:underline"
            >
              {contact.phone}
            </a>
          </li>
          {contact.homepage_url ? (
            <li>
              <a
                href={contact.homepage_url}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline-offset-2 hover:underline"
              >
                홈페이지
              </a>
            </li>
          ) : null}
          <li className="text-muted-foreground">
            주차 {contact.parking_available ? "가능" : "불가"}
          </li>
        </ul>
        {contact.appointment_methods.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1">
            <span className="text-xs text-muted-foreground">예약:</span>
            {contact.appointment_methods.map((m) => (
              <Badge key={m} variant="outline">
                {APPT_LABEL[m]}
              </Badge>
            ))}
          </div>
        ) : null}
      </div>
    </Section>
  );
}
