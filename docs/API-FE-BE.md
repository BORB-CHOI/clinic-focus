# API 명세: FE ↔ BE

> 하재원(프론트) ↔ 김경재(백엔드) 간 인터페이스 정의

---

## 기본 정보

- **베이스 URL (로컬 개발)**: `http://localhost:8000`
- **베이스 URL (배포)**: `https://{api-gateway-id}.execute-api.ap-northeast-2.amazonaws.com` (CloudFront 경유 시 `/api` prefix)
- **인증**: 없음 (모든 endpoint public)
- **요청·응답 포맷**: JSON (`Content-Type: application/json`)
- **문자 인코딩**: UTF-8
- **타임존**: 모든 시각은 ISO 8601 UTC (예: `2026-05-16T03:24:00Z`)
- **OpenAPI 스펙**: FastAPI 자동 생성, `/docs` 또는 `/openapi.json`에서 확인. 프론트는 `openapi-typescript`로 자동 타입 생성

---

## 공통 응답 형식

### 성공
```json
{
  "data": { ... },
  "meta": { ... }   // 선택, 페이지네이션·총 개수 등
}
```

### 에러
```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "검색 키워드가 비어있습니다",
    "details": { ... }   // 선택
  }
}
```

### 표준 에러 코드

| 코드 | HTTP | 의미 |
|---|---|---|
| `INVALID_PARAMETER` | 400 | 쿼리·바디 파라미터 부적합 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `DUPLICATE_FEEDBACK` | 409 | 동일 디바이스에서 동일 병원에 이미 피드백 |
| `INTERNAL_ERROR` | 500 | 서버 내부 에러 |
| `AI_SERVICE_ERROR` | 502 | Bedrock·Knowledge Base 호출 실패 |

---

## 공통 데이터 타입

### `Hospital`
```typescript
{
  hospital_id: string;            // UUID 또는 고유 식별자
  name: string;                   // 병원명
  standard_specialty: string;     // 표준 진료과목 ('피부과', '정형외과' 등)
  primary_focus: string[];        // 실제 주력 분야 태그 (다중 가능)
                                  // 예: ["미용 시술"] 또는 ["어깨·견관절", "스포츠 의학"]
  confidence: Confidence;         // 신뢰도 정보
  location: Location;
  website_url: string | null;
  one_line_summary: string;       // 검색 카드용 한 줄 요약 (AI 생성)
                                  // 예: "일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원"
  thumbnail_url: string | null;   // 병원 대표 이미지 URL. FE 카드 썸네일 + 헤드라이너 히어로
                                  // 미수집 단계에서는 null. FE 는 그라데이션 + 이니셜 폴백
}
```

> 검색 카드는 `one_line_summary` 한 줄을 노출하고, 상세 페이지에서는 별도의 `ai_description` (다단락 자연어 설명) 필드를 사용한다 (아래 상세 API 참조).

### `Confidence`
```typescript
{
  score: number;                  // 0~100
  level: "확실" | "추정" | "정보 부족";  // 95+ / 70~95 / <70
  signals: {
    self_claim: number;           // 자칭 컨셉 기여도 (0~100)
    vision: number;               // AI Vision 기여도
    blog: number;                 // 블로그 키워드 기여도
    reviews: number;              // 후기 키워드 기여도
  };
}
```

### `Location`
```typescript
{
  address: string;                // 전체 주소
  sido: string;                   // 시도 (예: "서울특별시")
  sigungu: string;                // 시군구 (예: "마포구")
  dong: string | null;            // 동
  lat: number;
  lng: number;
}
```

### `ClassificationChange`
```typescript
{
  changed_at: string;             // ISO 8601
  from_focus: string[];
  to_focus: string[];
  reason: "feedback_accumulated" | "human_review" | "vision_reanalysis" | "scheduled_recrawl";
  notes: string | null;
}
```

### 상세 페이지 영역별 타입

#### `Service` — 다루는 진료 항목
```typescript
{
  name: string;                   // "아토피", "여드름", "사마귀 냉동치료"
  category: "general" | "cosmetic" | "surgery" | "exam" | "other";
  source_signals: string[];       // ["self_claim", "blog", "vision"]
}
```

#### `ExcludedService` — 다루지 않는 분야
```typescript
{
  name: string;                   // "M자 탈모 처방"
  reason: "no_equipment" | "no_mention" | "low_signal";
  alternative_hospital_ids: string[];  // 동네 대안 병원 (⑧ 영역과 연결)
}
```

#### `Equipment` — 보유 의료기기
```typescript
{
  name: string;                   // "사마귀 냉동치료기"
  available: boolean;
  source: "vision" | "public_registry" | "self_claim";
  source_url: string | null;
}
```

#### `PriceItem` — 비급여 가격
```typescript
{
  service_name: string;           // "라식"
  price_range: string;            // "150만원~200만원"
  source_url: string;             // 사이트에서 추출한 출처
  last_seen: string;              // ISO 8601, 마지막 확인 시각
}
```

#### `Doctor` — 의료진
```typescript
{
  name: string;
  position: string;               // "원장", "부원장", "전문의"
  specialty_certifications: string[];  // 심평원 전문의 자격
  sub_specialty: string | null;   // 사이트에서 추출. "어깨 관절 세부전공"
  career: string[];               // ["서울대 의대 졸업", "○○병원 정형외과 수련"]
  primary_focus: string[] | null; // 의사별로 다른 경우만
  source_url: string | null;
}
```

#### `OperatingHours` — 운영시간
```typescript
{
  weekday: {                      // 월~금
    open: string;                 // "09:00"
    close: string;                // "18:00"
    lunch_start: string | null;
    lunch_end: string | null;
  };
  saturday: { open, close, lunch_start, lunch_end } | null;
  sunday: { open, close, lunch_start, lunch_end } | null;
  night_clinic: boolean;          // 야간 진료 여부
  holiday_clinic: boolean;        // 공휴일 진료 여부
}
```

#### `Contact` — 연락처·접근성
```typescript
{
  phone: string;
  homepage_url: string | null;
  parking_available: boolean;
  appointment_methods: ("walk_in" | "phone" | "online")[];
}
```

#### `FeedbackStats` — 사용자 피드백 누적 통계
```typescript
{
  total_count: number;
  agree_count: number;
  disagree_count: number;
  agree_ratio: number;            // 0~1
  last_feedback_at: string | null;
}
```

#### `RelatedHospital` — 관련 병원 추천
```typescript
{
  hospital_id: string;
  name: string;
  primary_focus: string[];
  similarity_score: number;       // 0~1
  recommendation_type: "same_focus" | "fills_gap";  // 같은 주력 / 빈자리 보완
  distance_km: number | null;
  thumbnail_url: string | null;   // 카드 썸네일용. 미수집이면 null (FE 가 폴백 처리)
}
```

#### `DataMetadata` — 메타 정보
```typescript
{
  last_updated_at: string;        // ISO 8601
  data_sources: ("self_site" | "public_registry" | "user_reviews" | "blog")[];
  data_completeness: number;      // 0~1, 9개 영역 중 채워진 비율
  warning: string | null;         // "정보 부족 — 직접 병원에 문의 권장" 등
}
```

---

## 엔드포인트

### 1. 검색

```
GET /api/search
```

자연어 쿼리 또는 위치 기반 검색. 두 방식이 결합 가능 — 자연어 + 위경도 함께 보내면 의미 매칭 + 지리적 필터링 동시 적용.

#### 쿼리 파라미터

| 이름 | 타입 | 필수 | 설명 |
|---|---|:---:|---|
| `q` | string | △ | 자연어 쿼리. 예: "M자 탈모 처방받을 수 있는 동네 의원" |
| `lat` | number | △ | 사용자 위도. 지도 검색 시 필수 |
| `lng` | number | △ | 사용자 경도. 지도 검색 시 필수 |
| `radius_km` | number | × | 검색 반경. `lat`/`lng`와 함께 사용. 기본 3, 최대 30 |
| `sido` | string | × | 시도 필터 (위경도와 함께 쓰면 위경도 우선) |
| `sigungu` | string | × | 시군구 필터 |
| `specialty` | string | × | 표준 진료과목 필터 |
| `min_confidence` | number | × | 최소 신뢰도 (기본 70) |
| `sort` | string | × | `distance` (기본, 위경도 있을 때) / `confidence` / `relevance` (자연어 검색 시) |
| `limit` | number | × | 결과 개수 (기본 20, 최대 50) |
| `offset` | number | × | 페이지네이션 (기본 0) |

> `q`와 `lat`/`lng` 중 **최소 하나는 필수**. 둘 다 있으면 의미 검색 결과를 반경 내로 필터링한다.

#### 응답 (200)
```json
{
  "data": [
    {
      "hospital_id": "h_abc123",
      "name": "○○피부과의원",
      "standard_specialty": "피부과",
      "primary_focus": ["일반 진료 (아토피·여드름)"],
      "confidence": {
        "score": 92,
        "level": "확실",
        "signals": { "self_claim": 35, "vision": 28, "blog": 17, "reviews": 12 }
      },
      "distance_km": 0.8,
      "location": {
        "address": "서울특별시 마포구 ...",
        "sido": "서울특별시",
        "sigungu": "마포구",
        "dong": "공덕동",
        "lat": 37.5443,
        "lng": 126.9510
      },
      "website_url": "https://...",
      "one_line_summary": "일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원",
      "thumbnail_url": null
    }
  ],
  "meta": {
    "total": 47,
    "limit": 20,
    "offset": 0,
    "search_mode": "natural+nearby",   // "natural" / "nearby" / "natural+nearby"
    "query_interpretation": "탈모 진료 / 의원급",
    "center": { "lat": 37.5443, "lng": 126.9510 },
    "radius_km": 3,
    "sort": "distance"
  }
}
```

#### 에러 예시
```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "q 또는 lat/lng 중 최소 하나는 필수입니다"
  }
}
```

---

### 2. 병원 상세

```
GET /api/hospitals/{hospital_id}
```

**본 서비스의 핵심 endpoint.** 단순 데이터 조각이 아니라 AI가 4 시그널을 종합해 생성한 자연어 통합 설명(`ai_description`)을 반환한다. 프론트의 상세 페이지는 이 설명을 최상단에 노출하고, 그 아래에 신뢰도·근거 시그널·변경 이력을 보조 자료로 깔아준다.

#### 경로 파라미터

| 이름 | 타입 | 설명 |
|---|---|---|
| `hospital_id` | string | 병원 ID |

#### 응답 (200)

응답은 상세 페이지 9개 영역에 직접 매핑된다. 영역 ①은 `ai_description`, 영역 ②는 `services` / `excluded_services` / `equipment` / `prices`, 영역 ③은 `doctors`, 영역 ④는 `confidence` + `detailed_signals`, 영역 ⑤는 `location` + `operating_hours` + `contact`, 영역 ⑥은 `feedback_stats`, 영역 ⑦은 `recent_changes`, 영역 ⑧은 `related_hospitals`, 영역 ⑨는 `metadata`.

```json
{
  "data": {
    "hospital_id": "h_abc123",
    "name": "○○피부과의원",
    "standard_specialty": "피부과",
    "primary_focus": ["일반 진료 (아토피·여드름)"],
    "confidence": { ... },
    "location": { ... },
    "website_url": "https://...",
    "one_line_summary": "일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원",
    "thumbnail_url": null,

    "ai_description": {
      "headline": "○○피부과는 일반 피부 진료 중심의 동네 의원입니다.",
      "paragraphs": [
        {
          "text": "홈페이지 메인 화면에서 아토피·여드름·습진 같은 일반 피부질환을 가장 먼저 안내하고 있으며, 시술 사진 80%가 일반 진료 케이스(피부 발진·습진·여드름)고 미용 시술 사진은 18%로 적습니다. 블로그 글 50건 중 아토피 관련 글이 34%, 여드름 관련 글이 21%로 가장 많고, 미용 시술 관련 글은 5건뿐입니다.",
          "citations": ["self_claim", "vision", "blog"]
        },
        {
          "text": "실제 방문 후기에서도 '친절한 아토피 상담', '꼼꼼한 여드름 치료' 같은 키워드가 자주 등장합니다. 다만 사마귀 냉동치료기·점 제거 레이저 같은 시술 장비는 보유하고 있지 않은 것으로 보이므로, 미용 목적이라면 다른 병원을 권합니다.",
          "citations": ["reviews", "vision"]
        }
      ],
      "generated_at": "2026-04-12T08:00:00Z",
      "generator_model": "global.anthropic.claude-sonnet-4-6"
    },
    // PoC 한도: 시연 10개 외 9990개 병원은 "ai_description": null 로 반환됨
    // FE는 null이면 헤드라이너 영역을 태그 카드로 차등 렌더링 (아래 "프론트 렌더링 가이드" 참조)

    "services": [
      { "name": "아토피", "category": "general", "source_signals": ["self_claim", "blog", "reviews"] },
      { "name": "여드름", "category": "general", "source_signals": ["self_claim", "blog", "reviews"] },
      { "name": "습진", "category": "general", "source_signals": ["self_claim", "blog"] }
    ],

    "excluded_services": [
      {
        "name": "사마귀 냉동치료",
        "reason": "no_equipment",
        "alternative_hospital_ids": ["h_def456", "h_ghi789"]
      },
      {
        "name": "M자 탈모 처방",
        "reason": "no_mention",
        "alternative_hospital_ids": ["h_jkl012"]
      }
    ],

    "equipment": [
      { "name": "더모스코프", "available": true, "source": "vision", "source_url": "https://.../about" },
      { "name": "사마귀 냉동치료기", "available": false, "source": "vision", "source_url": null },
      { "name": "점 제거 레이저", "available": false, "source": "vision", "source_url": null }
    ],

    "prices": [
      { "service_name": "점 빼기", "price_range": "5만원~", "source_url": "https://.../price", "last_seen": "2026-04-12T08:00:00Z" }
    ],

    "doctors": [
      {
        "name": "김○○",
        "position": "원장",
        "specialty_certifications": ["피부과 전문의"],
        "sub_specialty": "아토피·습진",
        "career": ["서울대 의대 졸업", "○○병원 피부과 수련"],
        "primary_focus": null,
        "source_url": "https://.../doctor/1"
      }
    ],

    "detailed_signals": {
      "self_claim": {
        "extracted_keywords": ["아토피", "여드름", "습진"],
        "source_text": "본원은 일반 피부 진료를 중심으로...",
        "source_url": "https://.../about"
      },
      "vision": {
        "detected_devices": ["더모스코프"],
        "image_distribution": { "일반 진료": 0.78, "미용 시술": 0.18, "기타": 0.04 },
        "sample_image_urls": ["https://.../img1.jpg", "https://.../img2.jpg"]
      },
      "blog": {
        "top_topics": [
          { "topic": "아토피", "frequency": 0.34 },
          { "topic": "여드름", "frequency": 0.21 }
        ],
        "total_posts": 50
      },
      "reviews": {
        "review_count": 142,
        "top_keywords": ["친절", "아토피", "여드름", "꼼꼼"]
      }
    },

    "operating_hours": {
      "weekday": { "open": "09:00", "close": "18:00", "lunch_start": "13:00", "lunch_end": "14:00" },
      "saturday": { "open": "09:00", "close": "13:00", "lunch_start": null, "lunch_end": null },
      "sunday": null,
      "night_clinic": false,
      "holiday_clinic": false
    },

    "contact": {
      "phone": "02-1234-5678",
      "homepage_url": "https://...",
      "parking_available": true,
      "appointment_methods": ["walk_in", "phone"]
    },

    "feedback_stats": {
      "total_count": 145,
      "agree_count": 126,
      "disagree_count": 19,
      "agree_ratio": 0.87,
      "last_feedback_at": "2026-05-15T14:22:00Z"
    },

    "recent_changes": [
      {
        "changed_at": "2026-04-12T08:00:00Z",
        "from_focus": ["미용 시술"],
        "to_focus": ["일반 진료 (아토피·여드름)"],
        "reason": "feedback_accumulated",
        "notes": "👎 피드백 18건 누적으로 재분류"
      }
    ],

    "related_hospitals": [
      {
        "hospital_id": "h_def456",
        "name": "△△피부과",
        "primary_focus": ["일반 진료 (아토피·여드름)"],
        "similarity_score": 0.91,
        "recommendation_type": "same_focus",
        "distance_km": 0.8,
        "thumbnail_url": null
      },
      {
        "hospital_id": "h_ghi789",
        "name": "□□피부과",
        "primary_focus": ["사마귀·점 제거"],
        "similarity_score": 0.42,
        "recommendation_type": "fills_gap",
        "distance_km": 1.2,
        "thumbnail_url": null
      }
    ],

    "metadata": {
      "last_updated_at": "2026-04-12T08:00:00Z",
      "data_sources": ["self_site", "public_registry", "user_reviews", "blog"],
      "data_completeness": 0.82,
      "warning": null
    }
  }
}
```

#### 영역별 필드 매핑

| 영역 | 응답 필드 |
|---|---|
| ① 헤드라이너 | `ai_description`, `confidence`, `one_line_summary` |
| ② 핵심 진료 정보 | `services`, `excluded_services`, `equipment`, `prices`, `primary_focus`, `standard_specialty` |
| ③ 의료진 정보 | `doctors` |
| ④ 신뢰도·근거 | `confidence`, `detailed_signals` |
| ⑤ 기본 운영 정보 | `location`, `operating_hours`, `contact` |
| ⑥ 사용자 피드백 | `feedback_stats` (피드백 제출은 별도 `POST /api/feedback`) |
| ⑦ 분류 변경 이력 | `recent_changes` (전체 이력은 별도 `GET /api/hospitals/{id}/history`) |
| ⑧ 관련 병원 추천 | `related_hospitals` |
| ⑨ 메타 정보 | `metadata` |

#### `ai_description` 필드 설명

| 필드 | 설명 |
|---|---|
| `headline` | 1문장 헤드라인. 상세 페이지 최상단에 큰 글씨로 노출 |
| `paragraphs` | 1~5개의 자연어 단락. 각 단락은 `text`(본문) + `citations`(이 단락이 참조한 시그널 키들) |
| `citations` 값 | `"self_claim"`, `"vision"`, `"blog"`, `"reviews"`, `"public_data"` 중 다중 |
| `generated_at` | 생성 시각. 시그널이 갱신되면 재생성 필요 |
| `generator_model` | 생성에 사용된 LLM 모델 ID (재현성·감사용) |

> **PoC 한도**: `ai_description`은 **시연 10개 병원만 값이 채워지고, 나머지는 `null`** 로 반환된다. 지원 계정 Bedrock 자원이 10개 한도라 `generate_description` LLM 호출도 10개 한정이기 때문 (자세한 건 `API-BE-AI.md` "2. `generate_description`" 참조). FE는 아래 차등 렌더링 로직을 따라야 한다.

#### 프론트 렌더링 가이드

**`ai_description`이 있을 때 (시연 10개 병원)**:

- `headline`은 상세 페이지 최상단에 강조 표시
- 각 `paragraphs[].text` 옆 또는 끝에 `citations` 시그널을 작은 배지로 표시 (예: `[사이트]` `[Vision]` `[블로그]` `[후기]`)
- 배지 클릭 시 `detailed_signals`의 해당 키 섹션으로 스크롤 또는 모달 오픈 → 사용자가 근거 자료를 직접 검토 가능
- **주체 명시 원칙**: `ai_description.paragraphs[].text`는 "이 병원이 자기 사이트에서 ~를 메인으로 표시함" 같은 표현만 등장하도록 최비성의 프롬프트에서 통제. 프론트는 이를 그대로 신뢰해 렌더

**`ai_description`이 `null`일 때 (9990개)**:

- 영역 ① 헤드라이너는 자연어 단락 대신 **태그 카드** 로 표시:
  - 표준 진료과목 + 룰 기반 자칭 컨셉 태그 (예: `피부과 · 미용 시술 · 아토피`)
  - 신뢰도 점수와 등급 ("추정 65%" / "정보 부족 45%")
  - "AI 자연어 설명은 시연 대상 10개 병원에 한정" 안내 한 줄
- 영역 ② 이하 다른 영역은 동일하게 렌더링 (룰 기반 데이터로도 다 채워짐)

**공통**:

- `excluded_services[].alternative_hospital_ids`는 영역 ⑧과 연결되므로, 다루지 않는 분야 옆에 "동네 대안: △△의원" 같은 링크 노출
- `metadata.warning`이 있으면 페이지 상단에 경고 배너 표시
- `metadata.data_completeness`가 0.6 미만이면 빈 영역은 "정보 부족" 표시

#### 에러 (404)
```json
{
  "error": { "code": "NOT_FOUND", "message": "병원을 찾을 수 없습니다" }
}
```

---

### 3. 분류 변경 이력

```
GET /api/hospitals/{hospital_id}/history
```

해당 병원의 분류가 시간에 따라 어떻게 바뀌었는지 반환. **평가요소 "투명성" 시연 핵심 endpoint.**

#### 응답 (200)
```json
{
  "data": [
    {
      "changed_at": "2026-04-12T08:00:00Z",
      "from_focus": ["미용 시술"],
      "to_focus": ["일반 진료 (아토피·여드름)"],
      "reason": "feedback_accumulated",
      "notes": "👎 피드백 18건 누적으로 재분류"
    },
    {
      "changed_at": "2026-01-15T03:30:00Z",
      "from_focus": [],
      "to_focus": ["미용 시술"],
      "reason": "scheduled_recrawl",
      "notes": "초기 분류"
    }
  ]
}
```

---

### 4. 피드백 제출

```
POST /api/feedback
```

검색·방문 후 사용자가 1-tap으로 분류 정확성을 평가. 익명 + localStorage `device_id` 기반 중복 방지.

#### 요청 바디
```json
{
  "hospital_id": "h_abc123",
  "device_id": "d_550e8400-e29b-41d4-a716-446655440000",
  "primary_focus": "일반 진료 (아토피·여드름)",
  "verdict": "agree" | "disagree",
  "comment": null   // 선택. 평가용에서는 사용 안 함
}
```

#### 필드 설명

| 필드 | 타입 | 필수 | 설명 |
|---|---|:---:|---|
| `hospital_id` | string | ○ | 평가 대상 병원 |
| `device_id` | string | ○ | 프론트가 localStorage에 저장한 UUID. 최초 방문 시 생성 |
| `primary_focus` | string | ○ | 평가 대상 태그 (그 병원의 현재 주력 분류 중 하나) |
| `verdict` | string | ○ | `agree` = 👍 / `disagree` = 👎 |
| `comment` | string | × | 추가 코멘트 (평가용 PoC에서는 미수집) |

#### 응답 (201)
```json
{
  "data": {
    "feedback_id": "f_xyz789",
    "received_at": "2026-05-16T03:24:00Z"
  }
}
```

#### 에러 (409)
```json
{
  "error": {
    "code": "DUPLICATE_FEEDBACK",
    "message": "이 디바이스에서 해당 병원에 이미 피드백을 제출했습니다"
  }
}
```

---

## 프론트 구현 가이드

### 디바이스 ID 생성·저장

```typescript
// utils/device.ts
const DEVICE_ID_KEY = 'app_device_id';

export function getDeviceId(): string {
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = 'd_' + crypto.randomUUID();
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}
```

### TanStack Query 사용 예시

```typescript
// hooks/useSearch.ts
import { useQuery } from '@tanstack/react-query';

export function useSearch(q: string, filters: SearchFilters) {
  return useQuery({
    queryKey: ['search', q, filters],
    queryFn: async () => {
      const params = new URLSearchParams({ q, ...filters });
      const res = await fetch(`/api/search?${params}`);
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    enabled: q.length > 0,
  });
}
```

### 타입 자동 생성

```bash
# BE가 /openapi.json을 제공하면
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
```

---

## CORS 설정 (BE 측)

프론트(CloudFront)와 BE(API Gateway)가 다른 도메인이라 CORS 허용 필요.

```python
# FastAPI 측
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://{cloudfront-domain}", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

---

## 버전 관리

- API 스펙 변경 시 본 문서 + FastAPI 코드 + OpenAPI 스펙 동시 업데이트
- Breaking change 발생 시 `/api/v2/...` 형태로 버전 prefix 분리
- 평가 단계에서는 v1 유지