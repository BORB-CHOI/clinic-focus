import type { HospitalDetail } from "@/types/domain";

// API-FE-BE.md "병원 상세" 응답을 기반으로 한 데모 Mock.
//
// 데이터는 9영역 위계 다듬기 라운드에 맞춰 풍성하게 확장했다:
//   - 의사 3명: 원장(아토피·습진 세부 전공) / 부원장(여드름 케어 + 의사별 primary_focus) / 진료의(일반)
//     · API 명세상 primary_focus 는 "의사별로 다른 경우만" 채움 → 한 명만 채워서 두 패턴 시각화
//   - 서비스: 진료과목별 4 카테고리 모두 등장
//   - excluded_services / equipment: 헛걸음 방지 시연 케이스
//   - 비급여 가격 다중 항목
//   - related_hospitals: same_focus 2 + fills_gap 2
//   - recent_changes 2건 (재분류 + 초기 분류)
//
// BE 연동 전까진 이 Mock 으로 9영역 화면 골격을 채운다.
export const mockHospital: HospitalDetail = {
  hospital_id: "h_abc123",
  name: "○○피부과의원",
  standard_specialty: "피부과",
  primary_focus: ["일반 진료 (아토피·여드름)"],
  confidence: {
    score: 92,
    level: "확실",
    signals: { self_claim: 35, vision: 28, blog: 17, reviews: 12 },
  },
  location: {
    address: "서울특별시 마포구 공덕동 1-2",
    sido: "서울특별시",
    sigungu: "마포구",
    dong: "공덕동",
    lat: 37.5443,
    lng: 126.951,
  },
  website_url: "https://example.com",
  one_line_summary: "일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원",

  ai_description: {
    headline: "○○피부과는 일반 피부 진료 중심의 동네 의원입니다.",
    paragraphs: [
      {
        text: "홈페이지 메인 화면에서 아토피·여드름·습진 같은 일반 피부질환을 가장 먼저 안내하고 있으며, 시술 사진 80%가 일반 진료 케이스(피부 발진·습진·여드름)고 미용 시술 사진은 18%로 적습니다. 블로그 글 50건 중 아토피 관련 글이 34%, 여드름 관련 글이 21%로 가장 많고, 미용 시술 관련 글은 5건뿐입니다.",
        citations: ["self_claim", "vision", "blog"],
      },
      {
        text: "실제 방문 후기에서도 '친절한 아토피 상담', '꼼꼼한 여드름 치료' 같은 키워드가 자주 등장합니다. 다만 사마귀 냉동치료기·점 제거 레이저 같은 시술 장비는 보유하고 있지 않은 것으로 보이므로, 미용 목적이라면 다른 병원을 권합니다.",
        citations: ["reviews", "vision"],
      },
    ],
    generated_at: "2026-04-12T08:00:00Z",
    generator_model: "anthropic.claude-sonnet-4-5-20250929-v1:0",
  },

  services: [
    {
      name: "아토피",
      category: "general",
      source_signals: ["self_claim", "blog", "reviews"],
    },
    {
      name: "여드름",
      category: "general",
      source_signals: ["self_claim", "blog", "reviews"],
    },
    {
      name: "습진",
      category: "general",
      source_signals: ["self_claim", "blog"],
    },
    {
      name: "지루성 피부염",
      category: "general",
      source_signals: ["self_claim", "blog"],
    },
    {
      name: "점 빼기",
      category: "cosmetic",
      source_signals: ["self_claim"],
    },
    {
      name: "피부 검사",
      category: "exam",
      source_signals: ["self_claim", "vision"],
    },
  ],

  excluded_services: [
    {
      name: "사마귀 냉동치료",
      reason: "no_equipment",
      alternative_hospital_ids: ["h_def456", "h_ghi789"],
    },
    {
      name: "M자 탈모 처방",
      reason: "no_mention",
      alternative_hospital_ids: ["h_jkl012"],
    },
    {
      name: "레이저 토닝",
      reason: "low_signal",
      alternative_hospital_ids: [],
    },
  ],

  equipment: [
    {
      name: "더모스코프",
      available: true,
      source: "vision",
      source_url: "https://example.com/about",
    },
    {
      name: "패치 테스트 키트",
      available: true,
      source: "self_claim",
      source_url: "https://example.com/about",
    },
    {
      name: "사마귀 냉동치료기",
      available: false,
      source: "vision",
      source_url: null,
    },
    {
      name: "점 제거 레이저",
      available: false,
      source: "vision",
      source_url: null,
    },
  ],

  prices: [
    {
      service_name: "점 빼기 (1mm 기준)",
      price_range: "5만원~",
      source_url: "https://example.com/price",
      last_seen: "2026-04-12T08:00:00Z",
    },
    {
      service_name: "패치 테스트",
      price_range: "8만원",
      source_url: "https://example.com/price",
      last_seen: "2026-04-12T08:00:00Z",
    },
    {
      service_name: "더모스코프 진단",
      price_range: "3만원",
      source_url: "https://example.com/price",
      last_seen: "2026-04-12T08:00:00Z",
    },
  ],

  doctors: [
    {
      name: "김가영",
      position: "원장 · 대표원장",
      specialty_certifications: ["피부과 전문의", "대한피부과학회 정회원"],
      sub_specialty: "아토피·습진",
      career: [
        "서울대학교 의과대학 졸업",
        "서울대학교병원 피부과 인턴·레지던트 수료",
        "대한피부과학회 학술대회 발표 (2022)",
      ],
      primary_focus: null,
      source_url: "https://example.com/doctor/1",
    },
    {
      name: "이서준",
      position: "부원장",
      specialty_certifications: ["피부과 전문의"],
      sub_specialty: "여드름·지루성 피부염",
      career: [
        "연세대학교 의과대학 졸업",
        "세브란스병원 피부과 수련",
        "○○피부과 합류 (2023)",
      ],
      // 이 의사만 진료 분야가 다른 케이스 — 의사별 primary_focus 가 전체와
      // 다르게 설정될 수 있다는 API 명세를 시각화
      primary_focus: ["여드름 케어", "지루성 피부염"],
      source_url: "https://example.com/doctor/2",
    },
    {
      name: "박지유",
      position: "진료의",
      specialty_certifications: ["피부과 전문의"],
      sub_specialty: null,
      career: ["고려대학교 의과대학 졸업", "고대안암병원 피부과 수련"],
      primary_focus: null,
      source_url: null,
    },
  ],

  detailed_signals: {
    self_claim: {
      extracted_keywords: ["아토피", "여드름", "습진", "지루성 피부염"],
      source_text:
        "본원은 일반 피부 진료를 중심으로, 아토피·여드름·습진 등 만성 피부 질환의 꾸준한 관리를 중요하게 생각합니다. 미용 시술보다는 환자분의 피부 상태를 오래 지켜보며 치료 방향을 잡는 진료를 지향합니다.",
      source_url: "https://example.com/about",
    },
    vision: {
      detected_devices: ["더모스코프", "패치 테스트 키트"],
      image_distribution: {
        "일반 진료": 0.78,
        "미용 시술": 0.18,
        기타: 0.04,
      },
      sample_image_urls: [
        "https://example.com/img1.jpg",
        "https://example.com/img2.jpg",
      ],
    },
    blog: {
      top_topics: [
        { topic: "아토피", frequency: 0.34 },
        { topic: "여드름", frequency: 0.21 },
        { topic: "습진", frequency: 0.12 },
        { topic: "지루성 피부염", frequency: 0.08 },
      ],
      total_posts: 50,
    },
    reviews: {
      review_count: 142,
      top_keywords: ["친절", "아토피", "여드름", "꼼꼼", "설명 자세함"],
    },
  },

  operating_hours: {
    weekday: {
      open: "09:00",
      close: "18:00",
      lunch_start: "13:00",
      lunch_end: "14:00",
    },
    saturday: {
      open: "09:00",
      close: "13:00",
      lunch_start: null,
      lunch_end: null,
    },
    sunday: null,
    night_clinic: false,
    holiday_clinic: false,
  },

  contact: {
    phone: "02-1234-5678",
    homepage_url: "https://example.com",
    parking_available: true,
    appointment_methods: ["walk_in", "phone"],
  },

  feedback_stats: {
    total_count: 145,
    agree_count: 126,
    disagree_count: 19,
    agree_ratio: 0.87,
    last_feedback_at: "2026-05-15T14:22:00Z",
  },

  recent_changes: [
    {
      changed_at: "2026-04-12T08:00:00Z",
      from_focus: ["미용 시술"],
      to_focus: ["일반 진료 (아토피·여드름)"],
      reason: "feedback_accumulated",
      notes: "👎 피드백 18건 누적으로 재분류",
    },
    {
      changed_at: "2026-01-15T03:30:00Z",
      from_focus: [],
      to_focus: ["미용 시술"],
      reason: "scheduled_recrawl",
      notes: "초기 분류",
    },
  ],

  related_hospitals: [
    {
      hospital_id: "h_def456",
      name: "△△피부과",
      primary_focus: ["일반 진료 (아토피·여드름)"],
      similarity_score: 0.91,
      recommendation_type: "same_focus",
      distance_km: 0.8,
    },
    {
      hospital_id: "h_jkl012",
      name: "공덕가족피부과",
      primary_focus: ["일반 진료 (아토피)"],
      similarity_score: 0.84,
      recommendation_type: "same_focus",
      distance_km: 1.0,
    },
    {
      hospital_id: "h_ghi789",
      name: "□□피부과",
      primary_focus: ["사마귀·점 제거"],
      similarity_score: 0.42,
      recommendation_type: "fills_gap",
      distance_km: 1.2,
    },
    {
      hospital_id: "h_mno345",
      name: "마포모발의원",
      primary_focus: ["탈모 처방", "두피 관리"],
      similarity_score: 0.31,
      recommendation_type: "fills_gap",
      distance_km: 0.9,
    },
  ],

  metadata: {
    last_updated_at: "2026-04-12T08:00:00Z",
    data_sources: ["self_site", "public_registry", "user_reviews", "blog"],
    data_completeness: 0.82,
    warning: null,
  },
};
