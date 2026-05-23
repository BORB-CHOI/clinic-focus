import type { HospitalDetail } from "@/types/domain";

// API-FE-BE.md "병원 상세" 응답 예시 그대로
// BE 연동 전까진 이 Mock으로 9영역 화면 골격을 채운다
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
      name: "점 빼기",
      category: "cosmetic",
      source_signals: ["self_claim"],
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
  ],

  equipment: [
    {
      name: "더모스코프",
      available: true,
      source: "vision",
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
      service_name: "점 빼기",
      price_range: "5만원~",
      source_url: "https://example.com/price",
      last_seen: "2026-04-12T08:00:00Z",
    },
  ],

  doctors: [
    {
      name: "김○○",
      position: "원장",
      specialty_certifications: ["피부과 전문의"],
      sub_specialty: "아토피·습진",
      career: ["서울대 의대 졸업", "○○병원 피부과 수련"],
      primary_focus: null,
      source_url: "https://example.com/doctor/1",
    },
  ],

  detailed_signals: {
    self_claim: {
      extracted_keywords: ["아토피", "여드름", "습진"],
      source_text:
        "본원은 일반 피부 진료를 중심으로, 아토피·여드름·습진 등 만성 피부 질환의 꾸준한 관리를 중요하게 생각합니다.",
      source_url: "https://example.com/about",
    },
    vision: {
      detected_devices: ["더모스코프"],
      image_distribution: { "일반 진료": 0.78, "미용 시술": 0.18, 기타: 0.04 },
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
      ],
      total_posts: 50,
    },
    reviews: {
      review_count: 142,
      top_keywords: ["친절", "아토피", "여드름", "꼼꼼"],
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
      hospital_id: "h_ghi789",
      name: "□□피부과",
      primary_focus: ["사마귀·점 제거"],
      similarity_score: 0.42,
      recommendation_type: "fills_gap",
      distance_km: 1.2,
    },
  ],

  metadata: {
    last_updated_at: "2026-04-12T08:00:00Z",
    data_sources: ["self_site", "public_registry", "user_reviews", "blog"],
    data_completeness: 0.82,
    warning: null,
  },
};
