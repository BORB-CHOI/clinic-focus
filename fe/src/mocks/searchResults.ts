import type { SearchResponse, SearchResultItem } from "@/types/domain";

// API-FE-BE.md "GET /api/search" 응답 예시 기준
// 시연을 위해 신뢰도 등급(확실/추정/정보 부족), 단일·다중 primary_focus,
// 거리 유무를 다양하게 섞어둠
//
// 첫 항목은 상세 페이지 Mock(`h_abc123`)과 같은 ID라
// 카드 클릭만으로 상세 페이지 9영역 데모로 이어진다
const mockSearchItems: SearchResultItem[] = [
  {
    hospital_id: "h_abc123",
    name: "○○피부과의원",
    standard_specialty: "피부과",
    primary_focus: ["일반 진료 (아토피·여드름)"],
    confidence: {
      score: 92,
      level: "확실",
      signals: { self_claim: 35, vision: 28, blog: 17, reviews: 12 },
    },
    distance_km: 0.8,
    location: {
      address: "서울특별시 마포구 공덕동 1-2",
      sido: "서울특별시",
      sigungu: "마포구",
      dong: "공덕동",
      lat: 37.5443,
      lng: 126.951,
    },
    website_url: "https://example.com",
    one_line_summary:
      "일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원",
  },
  {
    hospital_id: "h_def456",
    name: "△△피부과",
    standard_specialty: "피부과",
    primary_focus: ["일반 진료 (아토피·여드름)", "소아 피부 진료"],
    confidence: {
      score: 88,
      level: "추정",
      signals: { self_claim: 30, vision: 22, blog: 21, reviews: 15 },
    },
    distance_km: 1.4,
    location: {
      address: "서울특별시 마포구 도화동 12-3",
      sido: "서울특별시",
      sigungu: "마포구",
      dong: "도화동",
      lat: 37.5421,
      lng: 126.9468,
    },
    website_url: "https://example.com/def",
    one_line_summary:
      "이 병원이 자기 사이트에서 소아 아토피 진료 사례를 메인으로 소개함",
  },
  {
    hospital_id: "h_ghi789",
    name: "□□피부과",
    standard_specialty: "피부과",
    primary_focus: ["미용 시술"],
    confidence: {
      score: 96,
      level: "확실",
      signals: { self_claim: 40, vision: 32, blog: 12, reviews: 12 },
    },
    distance_km: 1.9,
    location: {
      address: "서울특별시 마포구 서교동 359",
      sido: "서울특별시",
      sigungu: "마포구",
      dong: "서교동",
      lat: 37.5519,
      lng: 126.9223,
    },
    website_url: "https://example.com/ghi",
    one_line_summary:
      "이 병원이 자기 사이트에서 보톡스·필러·레이저를 메인으로 표시함",
  },
  {
    hospital_id: "h_jkl012",
    name: "마포모발의원",
    standard_specialty: "피부과",
    primary_focus: ["탈모 진료"],
    confidence: {
      score: 81,
      level: "추정",
      signals: { self_claim: 28, vision: 14, blog: 23, reviews: 16 },
    },
    distance_km: 2.6,
    location: {
      address: "서울특별시 마포구 아현동 22",
      sido: "서울특별시",
      sigungu: "마포구",
      dong: "아현동",
      lat: 37.5544,
      lng: 126.9568,
    },
    website_url: "https://example.com/jkl",
    one_line_summary:
      "이 병원이 자기 블로그에서 M자 탈모 처방 사례를 다룸",
  },
  {
    hospital_id: "h_mno345",
    name: "공덕참피부과의원",
    standard_specialty: "피부과",
    primary_focus: ["사마귀·점 제거"],
    confidence: {
      score: 74,
      level: "추정",
      signals: { self_claim: 18, vision: 24, blog: 16, reviews: 16 },
    },
    distance_km: 0.5,
    location: {
      address: "서울특별시 마포구 공덕동 105",
      sido: "서울특별시",
      sigungu: "마포구",
      dong: "공덕동",
      lat: 37.5454,
      lng: 126.9532,
    },
    website_url: null,
    one_line_summary:
      "이 병원이 공식 신고한 의료기기 목록에 사마귀 냉동치료기가 포함됨",
  },
  {
    hospital_id: "h_pqr678",
    name: "신촌가족의원",
    standard_specialty: "가정의학과",
    primary_focus: [],
    confidence: {
      score: 52,
      level: "정보 부족",
      signals: { self_claim: 12, vision: 0, blog: 8, reviews: 32 },
    },
    distance_km: 3.1,
    location: {
      address: "서울특별시 서대문구 창천동 30",
      sido: "서울특별시",
      sigungu: "서대문구",
      dong: "창천동",
      lat: 37.5566,
      lng: 126.9387,
    },
    website_url: null,
    one_line_summary:
      "사이트가 없어 자칭 컨셉을 확인하기 어려움 — 직접 병원에 문의 권장",
  },
];

export const mockSearchResponse: SearchResponse = {
  data: mockSearchItems,
  meta: {
    total: mockSearchItems.length,
    limit: 20,
    offset: 0,
    search_mode: "natural+nearby",
    query_interpretation: "피부 진료 / 의원급",
    center: { lat: 37.5443, lng: 126.951 },
    radius_km: 3,
    sort: "distance",
  },
};
