// 도메인 타입 — API-FE-BE.md 기준
// M1 분류 스키마 동결 후에는 `npm run gen:api`로 자동 생성된 타입으로 대체
// 그 전까진 화면 골격 작업용으로 수동 정의

export type ConfidenceLevel = "확실" | "추정" | "정보 부족";
export type SignalKey =
  | "self_claim"
  | "vision"
  | "blog"
  | "reviews"
  | "public_data";

export interface ConfidenceSignals {
  self_claim: number;
  vision: number;
  blog: number;
  reviews: number;
}

export interface Confidence {
  score: number;
  level: ConfidenceLevel;
  signals: ConfidenceSignals;
}

export interface Location {
  address: string;
  sido: string;
  sigungu: string;
  dong: string | null;
  lat: number;
  lng: number;
}

export type ServiceCategory =
  | "general"
  | "cosmetic"
  | "surgery"
  | "exam"
  | "other";

export interface Service {
  name: string;
  category: ServiceCategory;
  source_signals: string[];
}

export type ExcludedReason = "no_equipment" | "no_mention" | "low_signal";

export interface ExcludedService {
  name: string;
  reason: ExcludedReason;
  alternative_hospital_ids: string[];
}

export type EquipmentSource = "vision" | "public_registry" | "self_claim";

export interface Equipment {
  name: string;
  available: boolean;
  source: EquipmentSource;
  source_url: string | null;
}

export interface PriceItem {
  service_name: string;
  price_range: string;
  source_url: string;
  last_seen: string;
}

export interface Doctor {
  name: string;
  position: string;
  specialty_certifications: string[];
  sub_specialty: string | null;
  career: string[];
  primary_focus: string[] | null;
  source_url: string | null;
}

export interface DayHours {
  open: string;
  close: string;
  lunch_start: string | null;
  lunch_end: string | null;
}

export interface OperatingHours {
  weekday: DayHours;
  saturday: DayHours | null;
  sunday: DayHours | null;
  night_clinic: boolean;
  holiday_clinic: boolean;
}

export type AppointmentMethod = "walk_in" | "phone" | "online";

export interface Contact {
  phone: string;
  homepage_url: string | null;
  parking_available: boolean;
  appointment_methods: AppointmentMethod[];
}

export interface FeedbackStats {
  total_count: number;
  agree_count: number;
  disagree_count: number;
  agree_ratio: number;
  last_feedback_at: string | null;
}

export type ChangeReason =
  | "feedback_accumulated"
  | "human_review"
  | "vision_reanalysis"
  | "scheduled_recrawl";

export interface ClassificationChange {
  changed_at: string;
  from_focus: string[];
  to_focus: string[];
  reason: ChangeReason;
  notes: string | null;
}

export type RecommendationType = "same_focus" | "fills_gap";

export interface RelatedHospital {
  hospital_id: string;
  name: string;
  primary_focus: string[];
  similarity_score: number;
  recommendation_type: RecommendationType;
  distance_km: number | null;
  /** 카드 썸네일용. null 이면 플레이스홀더 */
  thumbnail_url: string | null;
}

export type DataSource =
  | "self_site"
  | "public_registry"
  | "user_reviews"
  | "blog";

export interface DataMetadata {
  last_updated_at: string;
  data_sources: DataSource[];
  data_completeness: number;
  warning: string | null;
}

export interface AiDescriptionParagraph {
  text: string;
  citations: SignalKey[];
}

export interface AiDescription {
  headline: string;
  paragraphs: AiDescriptionParagraph[];
  generated_at: string;
  generator_model: string;
}

export interface DetailedSignals {
  self_claim: {
    extracted_keywords: string[];
    source_text: string;
    source_url: string;
  };
  vision: {
    detected_devices: string[];
    image_distribution: Record<string, number>;
    sample_image_urls: string[];
  } | null;
  blog: {
    top_topics: { topic: string; frequency: number }[];
    total_posts: number;
  };
  reviews: {
    review_count: number;
    top_keywords: string[];
  };
}

export interface HospitalDetail {
  hospital_id: string;
  name: string;
  standard_specialty: string;
  primary_focus: string[];
  confidence: Confidence;
  location: Location;
  website_url: string | null;
  one_line_summary: string;
  /**
   * 병원 대표 이미지 URL. 헤드라이너 히어로 + 검색·관련·지도 사이드 카드의
   * 좌측 썸네일에서 동일 출처로 사용. null 이면 그라데이션 + 이니셜 플레이스홀더.
   * BE 측 이미지 수집·저장 로직은 미구현 상태로 FE 는 자리만 비워둠.
   */
  thumbnail_url: string | null;

  ai_description: AiDescription | null;
  services: Service[];
  excluded_services: ExcludedService[];
  equipment: Equipment[];
  prices: PriceItem[];
  doctors: Doctor[];
  detailed_signals: DetailedSignals;
  operating_hours: OperatingHours | null;
  contact: Contact;
  feedback_stats: FeedbackStats;
  recent_changes: ClassificationChange[];
  related_hospitals: RelatedHospital[];
  metadata: DataMetadata;
}

// ── 검색 (GET /api/search) ───────────────────────────────────────────
// API-FE-BE.md "검색" 응답 기준
// 카드용 항목은 HospitalDetail의 헤더 필드 + distance_km 만 추려서 정의
// (상세 페이지 응답과 다른 엔드포인트라 별도 타입으로 분리)

export type SearchMode = "natural" | "nearby" | "natural+nearby";
export type SortOption = "distance" | "confidence" | "relevance";

export interface SearchResultItem {
  hospital_id: string;
  name: string;
  standard_specialty: string;
  primary_focus: string[];
  confidence: Confidence;
  /** 위경도 검색일 때만 채워짐 */
  distance_km: number | null;
  location: Location;
  website_url: string | null;
  one_line_summary: string;
  /** 병원 대표 이미지 URL. 카드 좌측 썸네일에서 사용. null 이면 플레이스홀더 */
  thumbnail_url: string | null;
}

export interface SearchMeta {
  total: number;
  limit: number;
  offset: number;
  search_mode: SearchMode;
  /** 자연어 쿼리 해석 결과 (자연어 검색일 때만) */
  query_interpretation: string | null;
  /** 위경도 검색일 때만 채워짐 */
  center: { lat: number; lng: number } | null;
  radius_km: number | null;
  sort: SortOption;
}

export interface SearchResponse {
  data: SearchResultItem[];
  meta: SearchMeta;
}
