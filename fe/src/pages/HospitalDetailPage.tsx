import { useEffect } from "react";
import { useParams } from "react-router-dom";

import { EmptyState } from "@/components/common/EmptyState";
import { WarningBanner } from "@/components/common/WarningBanner";
import { Tabs } from "@/components/common/Tabs";
import { HeadlinerSection } from "@/components/hospital/HeadlinerSection";
import { CoreServicesSection } from "@/components/hospital/CoreServicesSection";
import { DoctorsSection } from "@/components/hospital/DoctorsSection";
import { ConfidenceSection } from "@/components/hospital/ConfidenceSection";
import { BasicInfoSection } from "@/components/hospital/BasicInfoSection";
import { FeedbackSection } from "@/components/hospital/FeedbackSection";
import { RecentChangesSection } from "@/components/hospital/RecentChangesSection";
import { RelatedHospitalsSection } from "@/components/hospital/RelatedHospitalsSection";
import { MetadataSection } from "@/components/hospital/MetadataSection";
import { useHospitalDetail } from "@/hooks/useHospitalDetail";
import { trackSelect, trackAnalyticsSelect } from "@/lib/events";

// 병원 상세 페이지 — BE /api/hospitals/{id} 연동 (useHospitalDetail)
//
// 9영역을 3탭(기본/진료/운영·후기)으로 묶는다. 비-데모 병원은 ai_description·vision·
// operating_hours 가 null 일 수 있어 각 섹션이 null-safe 하게 렌더(차등 표시).
const TAB_ITEMS = [
  { value: "core", label: "진료 정보" },
  { value: "info", label: "기본 정보" },
  { value: "ops", label: "운영·후기" },
] as const;

type TabValue = (typeof TAB_ITEMS)[number]["value"];

export default function HospitalDetailPage() {
  const { hospitalId } = useParams();
  const { data: hospital, isLoading, isError, error } = useHospitalDetail(hospitalId);

  // 상세 페이지 진입 = select 이벤트 (가장 강한 전환 신호)
  useEffect(() => {
    if (!hospital) return;
    trackSelect(hospital.hospital_id);
    trackAnalyticsSelect(
      { hospitalId: hospital.hospital_id, hospitalName: hospital.name,
        standardSpecialty: hospital.standard_specialty,
        sigungu: hospital.location.sigungu },
      { lat: hospital.location.lat, lng: hospital.location.lng },
    );
  }, [hospital?.hospital_id]);

  if (isLoading) {
    return (
      <div className="py-24 text-center text-sm text-muted-foreground">
        병원 정보를 불러오는 중…
      </div>
    );
  }

  if (isError || !hospital) {
    return (
      <EmptyState
        message={`병원 정보를 불러오지 못했습니다 — ${
          (error as Error)?.message ?? "알 수 없는 오류"
        }`}
      />
    );
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{hospital.name}</h1>
          <p className="text-sm text-muted-foreground">
            {hospital.location.sigungu} · {hospital.standard_specialty}
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          ID: <code>{hospital.hospital_id}</code>
        </span>
      </header>

      {hospital.metadata.warning ? (
        <WarningBanner message={hospital.metadata.warning} />
      ) : null}

      {hospital.metadata.data_completeness < 0.6 ? (
        <WarningBanner
          message={`정보 충실도 ${Math.round(
            hospital.metadata.data_completeness * 100,
          )}% — 빈 영역이 많을 수 있습니다`}
        />
      ) : null}

      <Tabs<TabValue> defaultValue="core" items={TAB_ITEMS}>
        {{
          info: (
            <div className="space-y-4">
              <HeadlinerSection
                ai_description={hospital.ai_description}
                confidence={hospital.confidence}
                one_line_summary={hospital.one_line_summary}
                name={hospital.name}
                thumbnail_url={hospital.thumbnail_url}
              />
              <BasicInfoSection
                hospitalId={hospital.hospital_id}
                hospitalName={hospital.name}
                standardSpecialty={hospital.standard_specialty}
                location={hospital.location}
                operating_hours={hospital.operating_hours}
                contact={hospital.contact}
              />
              <MetadataSection metadata={hospital.metadata} />
            </div>
          ),
          core: (
            <div className="space-y-4">
              <CoreServicesSection
                standard_specialty={hospital.standard_specialty}
                primary_focus={hospital.primary_focus}
                services={hospital.services}
                excluded_services={hospital.excluded_services}
                equipment={hospital.equipment}
                prices={hospital.prices}
                related_hospitals={hospital.related_hospitals}
                sample_image_urls={
                  hospital.detailed_signals.vision?.sample_image_urls ?? []
                }
                hospital_name={hospital.name}
              />
              <DoctorsSection doctors={hospital.doctors} />
              <ConfidenceSection
                confidence={hospital.confidence}
                detailed_signals={hospital.detailed_signals}
              />
              <RecentChangesSection
                hospitalId={hospital.hospital_id}
                recent_changes={hospital.recent_changes}
              />
            </div>
          ),
          ops: (
            <div className="space-y-4">
              <FeedbackSection
                hospitalId={hospital.hospital_id}
                primary_focus={hospital.primary_focus}
                feedback_stats={hospital.feedback_stats}
              />
              <RelatedHospitalsSection
                related_hospitals={hospital.related_hospitals}
              />
            </div>
          ),
        }}
      </Tabs>
    </div>
  );
}
