import { useParams } from "react-router-dom";

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
import { mockHospital } from "@/mocks/hospital";

// 병원 상세 페이지 — 3탭 재구성
//
// 9영역을 의미 단위로 묶어 스크롤 길이를 줄이고 시연 흐름을 구분한다:
//   - 기본 정보  : ① 요약 + ⑤ 운영 + ⑨ 메타
//                  → "이 병원이 누구인지" 한 화면 도입부
//   - 진료 정보  : ② 핵심 진료 + ③ 의료진 + ④ 신뢰도 근거 + ⑦ 분류 변경 이력
//                  → 본 서비스 차별점이 응축. 데모 핵심 탭
//   - 운영·후기  : ⑥ 피드백 + ⑧ 관련 병원
//                  → 행동 유도 (피드백 1-tap, 대안 병원 진입)
//
// 활성 탭은 URL 쿼리(?tab=core / ?tab=ops)에 동기화 — 새로고침·공유 보존.
// 헤드라이너 citation 배지 → ④ 스크롤은 진료 정보 탭 안에서 자연스럽게 작동.
const TAB_ITEMS = [
  { value: "info", label: "기본 정보" },
  { value: "core", label: "진료 정보" },
  { value: "ops", label: "운영·후기" },
] as const;

type TabValue = (typeof TAB_ITEMS)[number]["value"];

export default function HospitalDetailPage() {
  const { hospitalId } = useParams();
  const hospital = mockHospital;

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

      <Tabs<TabValue>
        defaultValue="info"
        items={TAB_ITEMS}
      >
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
                  hospital.detailed_signals.vision.sample_image_urls
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
