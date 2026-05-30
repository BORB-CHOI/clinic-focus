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

> ⚠️ 현 구현 상태 (2026-05-26): `shared/models.py`의 `HospitalMeta`·`Classification`·`HospitalDescription` 어느 곳에도 `thumbnail_url` 필드가 정의돼 있지 않다. `be/api/search.py`/`be/api/hospital.py` 응답에도 `thumbnail_url` 키 자체가 누락. `one_line_summary`는 `HospitalDescription`에만 있어 description 미생성 9990개에서는 `""` 빈 문자열로 떨어진다 (명세는 `string` non-null 가정). 상세 페이지 `RelatedHospital`의 `thumbnail_url`도 마찬가지로 모델에 없음. V2 sprint **Phase A/D** 에서 모델·어댑터·응답 동시 정렬 예정.

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
  lat: number | null;
  lng: number | null;
  sido: string;                   // 시도 (예: "서울특별시")
  sigungu: string;                // 시군구 (예: "마포구")
}
```

### `ClassificationChange`
```typescript
{
  hospital_id: string;
  changed_at: string;             // ISO 8601
  from_focus: string[];
  to_focus: string[];
  reason: "feedback_accumulated" | "human_review" | "vision_reanalysis" | "scheduled_recrawl";
  notes: string | null;
  classifier_version: string;
}
```

### 상세 페이지 영역별 타입

#### `Service` — 다루는 진료 항목
```typescript
{
  name: string;                   // "아토피", "여드름", "사마귀 냉동치료"
  category: string;               // 자유 문자열 ("general", "cosmetic" 등 강제 enum 아님)
  source: "self_claim" | "vision" | "blog" | "reviews" | "public_data";  // 단일 출처
}
```

#### `ExcludedService` — 다루지 않는 분야
```typescript
{
  name: string;                   // "M자 탈모 처방"
  reason: string;                 // 자유 문자열 (강제 enum 아님)
  alternative_hospital_ids: string[];  // 동네 대안 병원 (⑧ 영역과 연결). 기본 [] 
}
```

##### `alternative_hospital_ids` 연결 동작 (V2)

영역 ② 의 `excluded_services` 와 영역 ⑧ 의 `related_hospitals[recommendation_type="fills_gap"]` 는 **같은 데이터의 두 표현**이다. AI 측 생성 흐름:

1. AI `extract_services_and_doctors(crawl_data, classification, vision_results)` 가 자체 사이트·외부 시그널·Vision 결과를 종합해 `excluded_services` 후보를 만든다 (예: "M자 탈모 처방", "사마귀 냉동치료" — 사이트 미언급 + 기기 미보유)
2. 각 항목에 대해 AI 가 `find_related_hospitals(excluded_services=...)` 를 호출 — 같은 시군구에서 그 분야를 *실제로 다루는* 병원을 KB Retrieve + 메타필터로 추출
3. 반환된 `hospital_id` 들을 해당 `ExcludedService.alternative_hospital_ids` 에 박고, 동일 후보를 `related_hospitals` 에 `recommendation_type="fills_gap"` 로도 박는다
4. `excluded_services` 항목 중 대안이 못 찾아진 경우 `alternative_hospital_ids: []` (빈 배열, `null` 아님)

FE 렌더링: 영역 ② "다루지 않는 분야" 카드에서 `alternative_hospital_ids` 가 비어있지 않으면 "M자 탈모 처방 ✗ — 동네 대안: △△의원" 식으로 hospital_id 별 링크를 노출. 클릭 시 해당 병원 상세 페이지로 이동.

#### `Equipment` — 보유 의료기기
```typescript
{
  name: string;                   // "사마귀 냉동치료기"
  source: "vision" | "public_data";
  confidence: number;             // 0~1
}
```

#### `PriceItem` — 비급여 가격
```typescript
{
  service_name: string;           // "라식"
  price_text: string;             // 원문 그대로 ("50,000원~")
}
```

#### `Doctor` — 의료진
```typescript
{
  name: string;
  specialty: string | null;       // 전문 진료과목
  qualifications: string[];        // 자격 (심평원 전문의 등). 기본 []
  sub_specialty: string | null;   // 사이트에서 추출. "어깨 관절 세부전공"
}
```

#### `OperatingHours` — 운영시간
```typescript
{
  weekday: string | null;         // "09:00~18:00" 등 원문 텍스트 (월~금)
  saturday: string | null;
  sunday: string | null;
  holiday: string | null;         // 공휴일 진료 텍스트
  lunch_break: string | null;     // "13:00~14:00" 등
}
```

#### `Contact` — 연락처·접근성
```typescript
{
  phone: string | null;
  website_url: string | null;
  reservation_url: string | null;
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
}
```

##### `recommendation_type` 두 케이스 V2 동작 명세

| 값 | 의미 | 산출 경로 |
|---|---|---|
| `same_focus` | 같은 시군구 + 같은 주력 분야의 유사 병원 | AI `find_related_hospitals` 가 KB Retrieve 로 같은 `primary_focus` 매칭 + 같은 `sigungu` 메타필터 → 유사도 상위 N |
| `fills_gap` | 이 병원이 **안 다루는 분야의 대안 병원** | AI `extract_services_and_doctors` 가 `excluded_services` 를 만들 때 각 항목별로 `find_related_hospitals(excluded_services=...)` 를 호출해서 받아낸 후보. 그 `hospital_id` 들이 `excluded_services[].alternative_hospital_ids` 에 동시 박힘 (영역 ②) |

FE 렌더링 가이드: 두 타입을 **시각적으로 분리해서 표시**한다.

- `same_focus` 카드 섹션 — "같은 주력 동네 병원" 헤더 + 유사도 막대
- `fills_gap` 카드 섹션 — "이 병원이 안 다루는 분야의 대안" 헤더 + 어떤 `excluded_services.name` 의 대안인지 라벨 박음
- 두 섹션 사이에 명확한 구분선·헤더 — 사용자가 "동일 대안" 과 "보완 대안" 을 혼동하지 않게

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
| `sort` | string | × | `relevance` (기본) / `distance` (위경도 있을 때 권장) / `confidence` |
| `limit` | number | × | 결과 개수 (기본 20, 최대 50) |
| `offset` | number | × | 페이지네이션 (기본 0) |

> `q`·`lat`/`lng`·(`sigungu`+`specialty`) 세 조합 중 **최소 하나는 필수**. 처리 경로는 아래 "`meta.search_mode` 4 모드 분기" 표 참조. `q` + `lat`/`lng` 동시 사용 시 의미 검색 결과를 반경 내로 필터링한다.

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
        "lat": 37.5443,
        "lng": 126.9510
      },
      "website_url": "https://...",
      "one_line_summary": "일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원",
      "matched_focus": ["탈모"]
    }
  ],
  "meta": {
    "total": 47,
    "limit": 20,
    "offset": 0,
    "search_mode": "natural+nearby",   // "natural" / "nearby" / "natural+nearby" / "category"
    "query_interpretation": "탈모 진료 / 의원급",
    "sort": "distance"
  }
}
```

#### 에러 예시
```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "q, lat/lng, sigungu 중 최소 하나는 필수입니다"
  }
}
```

#### `meta.search_mode` 4 모드 분기 (V2)

요청 파라미터 조합에 따라 BE 가 분기. `search_mode` 는 응답 `meta` 에 정확히 어느 경로로 처리됐는지 박는다.

| 모드 | 트리거 조건 | 처리 경로 | AI 경유 | 정렬 기본 |
|---|---|---|---|---|
| `natural` | `q` O / `lat,lng` X | AI `retrieve_hospital(SearchQuery)` → KB Retrieve | O | `relevance` |
| `nearby` | `q` X / `lat,lng` O | DDB `geo-index` bounding box + haversine 재계산 | X | `distance` |
| `natural+nearby` | `q` O / `lat,lng` O | KB Retrieve 결과를 반경 내로 필터링 (KB filter 에 lat/lng bounding) | O | `distance` |
| `category` | `q` X / `lat,lng` X / `sigungu`+`specialty` 만 O | DDB `sigungu-specialty-index` GSI 직접 조회, AI 미경유 | X | `confidence` |

`category` 모드는 V2 신규 — `q` 없이 사용자가 시군구·진료과목만 골라 카테고리 목록을 훑는 경우. 자연어 검색 비용·지연을 피하려고 DDB GSI 로 직접 처리한다 (`docs/plans/task-queue.md` §3-3 `sigungu-specialty-index`, `CLAUDE.md` "검색 경로 이원화").

위 4 조건에 다 부합 안 하면 (예: `q` X, `lat/lng` X, `sigungu`/`specialty` 도 X) 400 `INVALID_PARAMETER`.

> ℹ️ 현 코드 동작: `be/api/search.py` 의 검색 결과 카드(`_hospital_card`)는 META + CLASSIFICATION + DESCRIPTION 을 join 하되, **아직 분류·설명이 없는 병원**은 분류 필드를 placeholder 로 채운다 — `standard_specialty: ""`, `primary_focus: []`, `confidence: null`, `one_line_summary: ""`. 또한 검색 결과 카드에는 `thumbnail_url` 키 자체가 없다(위 상세 응답에만 존재). 분류 전 병원(9990개)에서 이 placeholder 들이 그대로 나오는 점을 FE 렌더링에서 의식할 것.

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
      "hospital_id": "h_abc123",
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
      "one_line_summary": "일반 피부 진료 중심, 미용 시술은 거의 안 하는 동네 의원",
      "generated_at": "2026-04-12T08:00:00Z",
      "generator_model": "global.anthropic.claude-sonnet-4-6"
    },
    // PoC 한도: 시연 10개 외 9990개 병원은 "ai_description": null 로 반환됨
    // FE는 null이면 헤드라이너 영역을 태그 카드로 차등 렌더링 (아래 "프론트 렌더링 가이드" 참조)

    "services": [
      { "name": "아토피", "category": "general", "source": "self_claim" },
      { "name": "여드름", "category": "general", "source": "self_claim" },
      { "name": "습진", "category": "general", "source": "blog" }
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
      { "name": "더모스코프", "source": "vision", "confidence": 0.92 },
      { "name": "사마귀 냉동치료기", "source": "vision", "confidence": 0.81 },
      { "name": "점 제거 레이저", "source": "vision", "confidence": 0.77 }
    ],

    "prices": [
      { "service_name": "점 빼기", "price_text": "50,000원~" }
    ],

    "doctors": [
      {
        "name": "김○○",
        "specialty": "피부과",
        "qualifications": ["피부과 전문의"],
        "sub_specialty": "아토피·습진"
      }
    ],

    "detailed_signals": {
      "self_claim": {
        "keywords": ["아토피", "여드름", "습진"],
        "primary_focus": ["일반 진료 (아토피·여드름)"],
        "spam_score": 0.08
      },
      "vision": {
        "detected_devices": ["더모스코프"],
        "image_categories": { "일반 진료": 0.78, "미용 시술": 0.18, "기타": 0.04 },
        "total_images_analyzed": 12
      },
      "blog": {
        "total_posts": 50,
        "keyword_frequency": { "아토피": 34, "여드름": 21 },
        "primary_topics": ["아토피", "여드름"]
      },
      "reviews": {
        "total_reviews": 142,
        "keyword_frequency": { "친절": 38, "아토피": 22, "여드름": 17, "꼼꼼": 14 },
        "primary_topics": ["친절", "아토피"]
      }
    },

    "operating_hours": {
      "weekday": "09:00~18:00",
      "saturday": "09:00~13:00",
      "sunday": null,
      "holiday": null,
      "lunch_break": "13:00~14:00"
    },

    "contact": {
      "phone": "02-1234-5678",
      "website_url": "https://...",
      "reservation_url": null
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
        "hospital_id": "h_abc123",
        "changed_at": "2026-04-12T08:00:00Z",
        "from_focus": ["미용 시술"],
        "to_focus": ["일반 진료 (아토피·여드름)"],
        "reason": "feedback_accumulated",
        "notes": "👎 피드백 18건 누적으로 재분류",
        "classifier_version": "rule-v1"
      }
    ],

    "related_hospitals": [
      {
        "hospital_id": "h_def456",
        "name": "△△피부과",
        "primary_focus": ["일반 진료 (아토피·여드름)"],
        "similarity_score": 0.91,
        "recommendation_type": "same_focus",
        "distance_km": 0.8
      },
      {
        "hospital_id": "h_ghi789",
        "name": "□□피부과",
        "primary_focus": ["사마귀·점 제거"],
        "similarity_score": 0.42,
        "recommendation_type": "fills_gap",
        "distance_km": 1.2
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

#### `detailed_signals` sub-block 명세 (영역 ④ 신뢰도·근거)

4 시그널 각각의 raw 데이터를 사용자에게 직접 노출 가능한 형태로 묶은 블록. 각 sub-block 은 해당 시그널이 비활성(데이터 없음)이면 `null`.

```typescript
detailed_signals: {
  self_claim: {                        // 필수 (null 아님)
    keywords: string[];                // 룰 기반 추출 자칭 키워드
    primary_focus: string[];           // 추론된 주력 분야
    spam_score: number;                // 0~1, 높을수록 자칭 도배 의심
  };
  vision: {                            // 시연 미대상이면 null
    detected_devices: string[];        // Vision 이 식별한 의료기기 (예: "더모스코프")
    image_categories: { [category: string]: number };  // 카테고리 -> 비율 (합=1.0)
    total_images_analyzed: number;     // 분석한 이미지 수
  } | null;
  blog: {                              // 필수 (null 아님)
    total_posts: number;               // 수집된 블로그 포스트 총수
    keyword_frequency: { [keyword: string]: number };  // 키워드 -> 등장 횟수
    primary_topics: string[];          // 상위 토픽
  };
  reviews: {                           // 필수 (null 아님)
    total_reviews: number;             // 합산 리뷰 총수
    keyword_frequency: { [keyword: string]: number };  // 키워드 -> 등장 횟수
    primary_topics: string[];          // 상위 토픽
  };
}
```

##### 의료법 §56③ — 후기 데이터 처리 (절대 어기지 말 것)

> **§56③ 환자 치료 경험담 광고 금지.** 후기 본문을 그대로 노출하면 의료법 위반 소지. 본 서비스는 키워드 빈도 통계만 사용자에게 노출한다.

| 항목 | 허용 | 금지 |
|---|---|---|
| 응답 필드 | `keyword_frequency` (키워드 -> 등장 횟수) · `total_reviews`/`total_posts` · `primary_topics` | 개별 리뷰 본문 (`review_text`·`review_body` 같은 필드) ❌ |
| FE 렌더링 | "친절·아토피 키워드 N건" 같은 통계 카드 / 키워드 클라우드 / 빈도 막대 차트 | 후기 본문 그대로 카드 표시 ❌ "○○님이 친절하다고 평가" 같은 인용 ❌ |
| 내부 저장 | DDB 에 raw 본문 보관 가능 (분석용) | API 응답에 raw 본문 통과 금지 |
| AI 설명 인용 | "후기 키워드 빈도 ~%" + 출처 배지 `[후기]` | "후기에서 호평" 같은 평가형 어조 ❌ |

블로그 sub-block 의 키워드 통계(`keyword_frequency`·`primary_topics`)만 화면에 노출하고, 후기·블로그 본문은 우리 화면에 옮겨오면 안 됨 — 사용자가 외부 원문에서 직접 읽도록 유도.

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

> ⚠️ 현 구현 상태 (`be/api/hospital.py`): `detailed_signals` 4 sub-block 필드명은 위 명세·예시가 `shared/models.py`(`SelfClaimSignal`·`VisionSignal`·`BlogSignal`·`ReviewSignal`)와 일치하며, `recent_changes` 항목도 모델 `ClassificationChange`(`hospital_id` + `classifier_version` 필수 포함)와 정합한다. 단 `metadata` 일부 필드는 아직 placeholder다.
> - `metadata.last_updated_at`은 `classification.classified_at`을 그대로 쓰며, classification 없으면 `null`.
> - `metadata.data_sources`는 현재 `["public_registry"]` 로 **하드코딩** — 위 예시처럼 실제 동원 소스를 동적 산출하는 건 미구현.
> - `metadata.data_completeness`는 9개 영역 채움 비율을 단순 가중치로 계산 (`be/api/hospital.py:_calc_completeness`).

---

### 3. 분류 변경 이력

```
GET /api/hospitals/{hospital_id}/history
```

해당 병원의 분류가 시간에 따라 어떻게 바뀌었는지 반환. **평가요소 "투명성" 시연 핵심 endpoint.**

#### V2 자동 기록 동작

`classify_hospital` 결과가 이전 `CLASSIFICATION` entity 와 달라지면 AI 모듈이 `HISTORY#{changed_at}` entity 를 자동 INSERT 한다 (`docs/plans/task-queue.md` §3-2, §4 Phase C "분류 변경 자동 기록"). 트리거:

- `feedback_accumulated` — `aggregate_feedback_stats` 가 임계 도달 + `recompute_confidence` 가 분류 변경
- `vision_reanalysis` — Vision 결과 갱신으로 분류 변경
- `scheduled_recrawl` — 정기 재크롤링으로 분류 변경 (초기 분류 포함)
- `human_review` — 수동 재분류

`recent_changes` (영역 ⑦) 는 본 엔드포인트와 동일 데이터의 최근 N건(기본 2) 으로 잘라낸 뷰. 전체 이력은 본 엔드포인트로만 조회.

#### 쿼리 파라미터

| 이름 | 타입 | 필수 | 설명 |
|---|---|:---:|---|
| `limit` | number | × | 반환할 이력 개수. 기본 10, 최대 50. 시간 역순(최신부터) |

#### 응답 (200)
```json
{
  "data": [
    {
      "hospital_id": "h_abc123",
      "changed_at": "2026-04-12T08:00:00Z",
      "from_focus": ["미용 시술"],
      "to_focus": ["일반 진료 (아토피·여드름)"],
      "reason": "feedback_accumulated",
      "notes": "👎 피드백 18건 누적으로 재분류",
      "classifier_version": "rule-v1"
    },
    {
      "hospital_id": "h_abc123",
      "changed_at": "2026-01-15T03:30:00Z",
      "from_focus": [],
      "to_focus": ["미용 시술"],
      "reason": "scheduled_recrawl",
      "notes": "초기 분류",
      "classifier_version": "rule-v1"
    }
  ]
}
```

> ⚠️ 현 구현 상태 (2026-05-26): `be/api/history.py`는 `load_recent_changes` 결과를 `model_dump()` 그대로 반환하므로 응답 항목에 모델 필수 필드 `classifier_version`과 `hospital_id`가 같이 포함된다 (위 예시 반영). DDB SK는 `HISTORY#{changed_at}` 포맷이라 ISO 8601 정렬은 정합. 본 문서 갱신으로 `limit` 쿼리 파라미터(기본 10, 최대 50)는 정식 스펙에 포함.

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
  "verdict": "agree",
  "comment": null
}
```

`verdict` 타입은 `Literal["agree", "disagree"]` — 그 외 값은 FastAPI 검증 실패로 422 (`VALIDATION_ERROR`) 응답. `comment` 는 요청 모델(`FeedbackRequest`)에 정의돼 있지 않아 현재 수집하지 않는다 (평가 PoC).

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

#### V2 동작 — 중복 방지 + 신뢰도 재계산 inline 호출

- **중복 체크 키**: `device_id + hospital_id` 조합. DDB single-table 에서 `PK=hospital_id, SK begins_with FEEDBACK#{device_id}` 쿼리로 동일 디바이스의 기존 피드백 1건이라도 발견되면 409. 같은 디바이스가 같은 병원에 두 번 평가하지 못한다 (다른 병원에는 각각 1회 가능).
- **저장 entity**: `FEEDBACK#{device_id}#{timestamp}` (`docs/plans/task-queue.md` §3-2). `verdict`·`primary_focus` 평가 대상·`received_at` 박힘.
- **임계 도달 시 재계산 inline 호출**:
  - 트리거 조건: 해당 병원의 누적 피드백 ≥ `RECOMPUTE_THRESHOLD`(현재 10건). disagree 비율 조건은 없음 (`be/core/feedback.py:should_recompute`)
  - BE 가 같은 요청 컨텍스트에서 `ai.recompute_confidence(hospital_id, all_feedback)` 를 동기 호출
  - 결과는 기존 `CLASSIFICATION` 의 `confidence` 만 교체 (분류 `primary_focus`·`standard_specialty` 는 유지). 현 구현은 `HISTORY#{changed_at}` 자동 INSERT 는 하지 않는다 (영역 ⑦ 자동 기록은 미연동)
  - **응답 지연**: 재계산이 트리거된 요청은 일반 ~50ms 대신 ~1s 추가될 수 있음. FE 는 1.5s 타임아웃·로딩 인디케이터로 대응
- 임계 미달 시는 `FEEDBACK#STATS` entity 만 증분 갱신, `recompute_confidence` 미호출 → 응답 빠름

> ⚠️ 현 구현 상태 (2026-05-29): `be/api/feedback.py`는 명세와 가장 정합한 엔드포인트. `db.check_duplicate_feedback(hospital_id, device_id)` (`be/adapters/dynamo_adapter.py:375`)로 중복 방지 동작하고 409 응답도 명세 그대로. `verdict` 는 요청 모델(`FeedbackRequest`)에서 `Literal["agree","disagree"]`로 받으므로 잘못된 값은 FastAPI 가 422 로 거른다. 임계치 도달 시 `_maybe_recompute_confidence` 가 `ai.recompute_confidence(hospital_id, all_feedback)` 를 inline 동기 호출해 기존 `CLASSIFICATION` 의 `confidence` 만 갱신한다(분류 자체는 유지). 다만 `should_recompute` 임계는 누적 10건 단순 기준이고 disagree 비율 조건은 아직 없으며, 분류 변경 `HISTORY` 자동 INSERT 는 미연동.

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
# be/handlers/api.py
import os
from fastapi.middleware.cors import CORSMiddleware

# 허용 오리진 — env CORS_ALLOW_ORIGINS(쉼표 구분) 우선, 기본은 FE 로컬 dev 서버.
# CloudFront 도메인은 배포 시 env 로 주입.
_default_origins = "http://localhost:5173"
_allow_origins = [
    o.strip()
    for o in os.environ.get("CORS_ALLOW_ORIGINS", _default_origins).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

> ⚠️ 현 구현 상태 (2026-05-26): `be/handlers/api.py`는 env CORS_ALLOW_ORIGINS allowlist(기본 localhost:5173) origins 와 GET/POST methods 로 제한돼 위 코드블록과 일치한다. 와일드카드는 allow_headers 만 적용 — 평가 PoC엔 OK.

---

## 버전 관리

- API 스펙 변경 시 본 문서 + FastAPI 코드 + OpenAPI 스펙 동시 업데이트
- Breaking change 발생 시 `/api/v2/...` 형태로 버전 prefix 분리
- 평가 단계에서는 v1 유지