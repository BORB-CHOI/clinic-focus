import { useParams } from "react-router-dom";

import { WarningBanner } from "@/components/common/WarningBanner";
import { HeadlinerSection } from "@/components/hospital/HeadlinerSection";
import { CoreServicesSection } from "@/components/hospital/CoreServicesSection";
import { DoctorsSection } from "@/components/hospital/DoctorsSection";
import { ConfidenceSection } from "@/components/hospital/ConfidenceSection";
import { BasicInfoSection } from "@/components/hospital/BasicInfoSection";
import { FeedbackSection } from "@/components/hospital/FeedbackSection";
import { RecentChangesSection } from "@/components/hospital/RecentChangesSection";
import { RelatedHospitalsSection } from "@/components/hospital/RelatedHospitalsSection";
import { MetadataSection } from "@/components/hospital/MetadataSection";
import { mockHospital } from "@/mocks/hospital";

// 병원 상세 페이지 — 데모 핵심 장면
// 9개 영역 ① ~ ⑨를 위에서 아래로 1:1 매핑
// 데이터는 Mock. M1 후 useQuery로 GET /api/hospitals/{id} 연결 예정
export default function HospitalDetailPage() {
  const { hospitalId } = useParams();
  const hospital = mockHospital;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-3xl font-bold">{hospital.name}</h1>
          <p className="text-sm text-muted-foreground">
            {hospital.location.sigungu} · {hospital.standard_specialty}
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          ID: <code>{hospitalId ?? hospital.hospital_id}</code>
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

      <HeadlinerSection
        ai_description={hospital.ai_description}
        confidence={hospital.confidence}
        one_line_summary={hospital.one_line_summary}
      />
      <CoreServicesSection
        standard_specialty={hospital.standard_specialty}
        primary_focus={hospital.primary_focus}
        services={hospital.services}
        excluded_services={hospital.excluded_services}
        equipment={hospital.equipment}
        prices={hospital.prices}
      />
      <DoctorsSection doctors={hospital.doctors} />
      <ConfidenceSection
        confidence={hospital.confidence}
        detailed_signals={hospital.detailed_signals}
      />
      <BasicInfoSection
        location={hospital.location}
        operating_hours={hospital.operating_hours}
        contact={hospital.contact}
      />
      <FeedbackSection
        hospitalId={hospital.hospital_id}
        primary_focus={hospital.primary_focus}
        feedback_stats={hospital.feedback_stats}
      />
      <RecentChangesSection
        hospitalId={hospital.hospital_id}
        recent_changes={hospital.recent_changes}
      />
      <RelatedHospitalsSection
        related_hospitals={hospital.related_hospitals}
      />
      <MetadataSection metadata={hospital.metadata} />
    </div>
  );
}
