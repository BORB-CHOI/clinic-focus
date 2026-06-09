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

/**
 * 심평원 신고 기준 운영시간 — BE shared/models.py OperatingHours 와 1:1 매핑.
 * 모든 필드 평문 string. 예: weekday="09:30~18:00", lunch_break="13:00~14:00",
 * sunday="휴진", parking_note="가능(무료)".
 * null 이면 해당 항목 신고 정보 없음.
 */
export interface OperatingHours {
  weekday: string | null;
  saturday: string | null;
  sunday: string | null;
  holiday: string | null;
  lunch_break: string | null;
  /** 심평원 getDtlInfo2.8 parkEtc — 주차 안내 텍스트 (예: "외래진료 30분 무료") */
  parking_note: string | null;
}

/** BE Contact — phone·website_url·reservation_url 세 필드만. */
export interface Contact {
  phone: string | null;
  website_url: string | null;
  reservation_url: string | null;
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

// ── 심평원 공공 신고 데이터 타입 ────────────────────────────────────────
// BE /api/hospitals/{id} 응답의 신규 필드. 키 미승인 시 빈값(빈 객체/빈 배열/null)으로 내려옴.
// FE 는 "데이터 있으면 표시, 없으면 영역 숨김" 으로 graceful 처리.
//
// ★ 임시 수동 보강 — BE 기동 후 openapi-typescript 재생성으로 대체 예정.
// 자동생성 명령: npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts

/** 심평원 신고 비급여 항목 1건 */
export interface NonPayItem {
  /** 비급여 항목명. 예: "도수치료 30분" */
  item_name: string;
  /** 항목 분류. 예: "도수·물리치료". null 이면 미분류 */
  category: string | null;
  /** 심평원 신고 금액(원). null 이면 신고 금액 없음 */
  amount: number | null;
}

export interface HospitalDetail {
  hospital_id: string;
  name: string;
  standard_specialty: string;
  /** 표시용 파생 카테고리 — standard_specialty='기타'면 primary_focus 로 도출한 하위
   * 카테고리(미용/모발·탈모/통증·근골격/수면 등). 그 외엔 standard_specialty 와 동일. */
  etc_subcategory?: string;
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

  // ── 심평원 공공 신고 데이터 (신규) ───────────────────────────────────
  /**
   * 심평원 신고 기준 과목별 전문의 수.
   * 예: { "피부과": 0, "가정의학과": 1 }
   * 키 미승인 시 빈 객체 {} 로 내려옴 → Object.keys 길이로 표시 여부 판단.
   */
  specialists_by_dept: Record<string, number>;
  /**
   * 심평원 신고 기준 총 의사 수.
   * null 이면 신고 데이터 없음.
   */
  total_doctors: number | null;
  /**
   * 심평원 신고 비급여 항목 목록.
   * 키 미승인 시 빈 배열 [] 로 내려옴 → length 로 표시 여부 판단.
   */
  nonpay_items: NonPayItem[];
}

// ── 검색 (GET /api/search) ───────────────────────────────────────────
// API-FE-BE.md "검색" 응답 기준
// 카드용 항목은 HospitalDetail의 헤더 필드 + distance_km 만 추려서 정의
// (상세 페이지 응답과 다른 엔드포인트라 별도 타입으로 분리)

export type SearchMode = "natural" | "nearby" | "natural+nearby" | "category";
export type SortOption = "distance" | "confidence" | "relevance" | "popular";

// ── 진료과목 (GET /api/specialties) ─────────────────────────────────────
export interface Specialty {
  specialty: string;
  count: number;
}

export interface SpecialtiesResponse {
  data: Specialty[];
  meta: {
    sigungu: string;
    total_hospitals: number;
    total_specialties: number;
  };
}

// ── 카테고리 트리 (GET /api/categories) ──────────────────────────────────
// L1 노드: specialty(표준 진료과) 또는 etc(기타에서 승격된 버킷)
// L2 sub: 세부 시술·증상 태그 (BE 에서 count 내림차순·최대 12개)
export interface CategorySubItem {
  label: string;
  count: number;
}

export interface CategoryNode {
  key: string;                   // L1 표시 라벨 (검색 파라미터 category= 로 그대로 사용)
  origin: "specialty" | "etc";  // specialty=표준 진료과, etc=기타 승격 버킷
  count: number;
  sub: CategorySubItem[];        // L2 세부 시술·증상 (최대 12개, count 내림차순)
}

export interface CategoriesResponse {
  data: CategoryNode[];
  meta: {
    sigungu: string;
    total_hospitals: number;
    total_categories: number;
  };
}

export interface SearchResultItem {
  hospital_id: string;
  name: string;
  standard_specialty: string;
  /** 표시용 파생 카테고리 — '기타'면 primary_focus 로 도출(미용/모발·탈모/통증·근골격…). */
  etc_subcategory?: string;
  primary_focus: string[];
  /** NL 검색 시 쿼리와 매칭된 주력 분야 키워드 */
  matched_focus: string[];
  /** 분류 전(미분류) 병원은 null — 카테고리·지도엔 노출되나 신뢰도/근거 없음 */
  confidence: Confidence | null;
  /** 위경도 검색일 때만 채워짐 */
  distance_km: number | null;
  location: Location;
  website_url: string | null;
  one_line_summary: string;
  /** 병원 대표 이미지 URL. 카드 좌측 썸네일에서 사용. null 이면 플레이스홀더 */
  thumbnail_url: string | null;
  /** 클릭률 (clicks / impressions). compute_event_scores.py 집계 기준 */
  ctr: number;
  /** 누적 클릭 수 */
  click_count: number;
}

// ── 심평원 필터용 검색 파라미터 보강 ────────────────────────────────────
// GET /api/search 신규 쿼리 파라미터 (카테고리/시군구 탐색 경로 전용).
// ★ 임시 수동 보강 — BE openapi-typescript 재생성으로 대체 예정.
export interface HiraSearchParams {
  /**
   * true 면 심평원 신고 기준 전문의 있는 병원만.
   * 카테고리/시군구 탐색(q 없는 category 모드)에서만 유효.
   * 자연어 q 있으면 BE 가 무시.
   */
  has_specialist?: boolean;
  /**
   * 특정 진료과 전문의 1명 이상 병원만.
   * 예: "피부과"
   */
  specialist_dept?: string;
}

export interface SearchMeta {
  total: number;
  limit: number;
  offset: number;
  /** 다음 페이지 존재 여부 (offset+limit < total) */
  has_more: boolean;
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
