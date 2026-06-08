# 데이터 해자 전략 & 구현 명세

> 최초 작성: 2026-06-03 · 최종 업데이트: 2026-06-03
> 상위 컨텍스트: [`../overview.md`](../overview.md) · [`../architecture.md`](../architecture.md) · [`task-queue.md`](task-queue.md)

---

## 1. 데이터 해자란 무엇인가

경쟁자가 단기간에 복제할 수 없는 데이터 자산.
클리닉포커스의 해자는 세 축으로 구성된다.

| 해자 축 | 설명 | 복제 난이도 |
|---|---|---|
| **자칭 컨셉 + 시간 이력** | 병원이 자기 사이트에서 뭘 강조했는지, 언제 어떻게 바뀌었는지 | 높음 — 크롤·AI 분류를 수년 누적해야 |
| **환경×시간×신체 × 검색 패턴** | 날씨·PM2.5·체감온도 등 환경 신호와 검색 행동의 교차 | 높음 — 트래픽 + 시간 없으면 생성 불가 |
| **피드백 보정 분류** | 유저 agree/disagree가 쌓여 AI 분류 신뢰도가 자동 개선 | 높음 — 사용자 수·시간에 비례 |

---

## 2. 경쟁 서비스 비교

| 서비스 | 핵심 해자 데이터 | 수집 방식 | 저장 구조 |
|---|---|---|---|
| **강남언니** | 시술 전후 사진 + 실제 후기 (UGC) | 유저 직접 등록 | S3(이미지) + RDS |
| **굿닥** | 실시간 대기시간 + 예약 전환율 | 병원 예약 시스템 연동 | RDBMS + Redis |
| **모두닥** | 증상별 병원 선택 패턴 + 영수증 인증 후기 | 검색→클릭→예약 퍼널 로그 | Redshift + MySQL |
| **네이버 플레이스** | 방문 인증 리뷰 + 실시간 혼잡도 | GPS + 결제 연동 | 분산 NoSQL + ES |
| **클리닉포커스** | **자칭 컨셉 + 환경 컨텍스트 × 검색 패턴** | 크롤 + AI 분류 + 이벤트 + 날씨 API | DynamoDB(2개) + S3 + Bedrock KB |

**클리닉포커스만 있는 것**: 환경 신호(날씨·PM2.5 등)와 의료 검색 패턴의 교차 데이터. 강남언니·굿닥·네이버 모두 없음.

---

## 3. 플라이휠 구조

```
        ① 수집                   ② 가공                  ③ 반영
┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────────┐
│ 크롤 (자체사이트)    │  │ 룰 분류 (강남 전수)  │  │ KB 벡터 검색        │
│ 카카오 후기/블로그   │→ │ 임베딩 → KB 적재     │→ │ + 주력 강도 랭킹    │
│ 심평원 공공 데이터   │  │ CTR/SCR 집계         │  │ + 이벤트 점수 보정  │
│ 기상청·에어코리아 API│  │ 환경 컨텍스트 집계   │  │ + 환경 패턴 인사이트 │
└─────────────────────┘  └──────────────────────┘  └─────────────────────┘
         ↑                                                    │
┌────────────────────────────────────────────────────────────┘
│  ④ 유저 루프 (해자 심화)
│  검색 → 노출(impression) → 클릭(click) → 상세진입(select)
│  상세 페이지 → 피드백(agree/disagree) → confidence 자동 재계산
│  전화 클릭 / 홈페이지 클릭 → 최종 전환 신호
│  검색어 × 환경 컨텍스트 패턴 누적 → 계절·날씨별 수요 인사이트
└────────────────────────────────────────────────────────────
```

---

## 4. 구현 현황 (2026-06-03 기준)

### ✅ 완료된 것

**Analytics 파이프라인 (신규)**
```
테이블: kmuproj-02-clinic-Analytics (신규 생성, Main과 완전 분리)
  HEALTH_EVENT   → 환경 컨텍스트 + 프로파일 포함 이벤트 저장 중 (942건)
  USER_PROFILE   → opt-in 건강 프로파일 저장 완료
  HEALTH_STATS   → STATS#INSIGHTS/LATEST 운영 인사이트 집계 저장

BE 신규 파일
  be/adapters/analytics_adapter.py  → Analytics 테이블 CRUD
  be/adapters/weather_adapter.py    → 기상청 + 에어코리아 API 연동
  be/api/analytics.py               → /api/analytics/events, /profile, /weather, /insights
  be/scripts/compute_health_stats.py      → raw 이벤트 집계
  be/scripts/seed_demo_analytics_events.py → 데모 이벤트 생성

FE 신규 파일
  fe/src/lib/healthProfile.ts               → BMI 버킷 계산 (FE only)
  fe/src/lib/events.ts                      → trackAnalyticsClick/Impression/Select 추가
  fe/src/components/analytics/HealthProfileModal.tsx → 내 정보 입력 모달
  fe/src/components/analytics/WeatherBadge.tsx      → 헤더 날씨 위젯
  fe/src/pages/InsightsPage.tsx             → 운영 인사이트 대시보드

환경 API
  KMAS_API_KEY=...        → 기상청 초단기실황 (활성화됨)
  AIRKOREA_API_KEY=...    → 에어코리아 PM2.5 (활성화됨)
  ANALYTICS_TABLE=kmuproj-02-clinic-Analytics
```

**이벤트 수집 범위 (연결 완료)**
```
impression   검색 결과 카드 노출 시
click        검색 결과 카드 클릭 / 지도 마커 클릭 / 리스트 카드 클릭
select       병원 상세 페이지 진입 (가장 강한 전환 신호)
             전화하기 클릭
             홈페이지 클릭
feedback     맞아요/아니에요 → /api/feedback (Main 테이블 저장)
```

**Main 테이블 (기존)**
```
테이블: kmuproj-02-team3-backend
  EVENT#{type}#{ts}       기존 impression/click/select 이벤트
  EVENT#STATS             CTR·SCR 배치 집계 (compute_event_scores.py)
  FEEDBACK#{id}           피드백 저장 + confidence 자동 재계산 (연결 완료)
  HISTORY#{iso}           분류 변경 이력
  CLASSIFICATION          강남 ~3098 분류 완료
```

### 남은 작업

| 항목 | 상태 |
|---|---|
| compute_health_stats.py | ✅ 작성 완료 — HEALTH_EVENT → STATS#INSIGHTS/LATEST |
| /insights 시각화 페이지 | ✅ 작성 완료 — 사이트 내부 운영 대시보드 |
| CTR/SCR → 검색 랭킹 반영 | be/api/search.py 미연결 |
| 일교차(temp_diff_bucket) | ✅ 기상청 단기예보 TMN/TMX + fallback 수집 |
| query 빈 문자열 정리 | 지도 탐색 시 "" 대신 null로 저장 필요 |

---

## 5. 실제 저장 변수 (AS-BUILT)

### Analytics 테이블 — HEALTH_EVENT

실제 DB에 저장되는 필드 전체:

```json
{
  "pk":                "EVENT#{device_id_sha256_16자}",
  "sk":                "EVENT#{type}#{iso_timestamp}",
  "event_id":          "uuid",
  "event_type":        "impression | click | select",
  "hospital_id":       "병원 고유 ID",
  "hospital_name":     "서울웰이비인후과의원",
  "standard_specialty": "이비인후과",
  "sigungu":           "강남구",
  "query":             "비염치료",
  "position":          2,

  "env": {
    "temp_bucket":       "cold|cool|mild|warm|hot",
    "feels_like_bucket": "cold|cool|mild|warm|hot",
    "temp_diff_bucket":  "small|normal|large|very_large|unknown",
    "humidity_bucket":   "dry|normal|humid",
    "pm25_bucket":       "good|moderate|bad|very_bad",
    "season":            "spring|summer|fall|winter",
    "time_bucket":       "dawn|morning|afternoon|evening",
    "day_type":          "weekday|weekend",
    "temp_c":            28.0,
    "feels_like_c":      28.8,
    "temp_diff_c":       12.0,
    "humidity_pct":      54.0,
    "pm25_value":        26.0,
    "wind_ms":           3.1,
    "is_raining":        false
  },

  "profile": {
    "gender_bucket":  "male|female|other|unknown",
    "age_bucket":     "teens|20s|30s|40s|50plus|unknown",
    "bmi_bucket":     "underweight|normal|overweight|obese|unknown"
  },

  "created_at":  "2026-06-03T02:36:43Z",
  "ttl":         "unix_timestamp (1년 후 자동 만료)"
}
```

### Analytics 테이블 — USER_PROFILE

```json
{
  "pk":            "PROFILE#{device_id_sha256_16자}",
  "sk":            "PROFILE",
  "gender_bucket": "male",
  "age_bucket":    "20s",
  "bmi_bucket":    "normal",
  "consented_at":  "2026-06-03T02:14:29Z"
}
```

### Main 테이블 — FEEDBACK

```json
{
  "hospital_id":    "병원 고유 ID",
  "entity":         "FEEDBACK#{feedback_uuid}",
  "verdict":        "agree|disagree",
  "primary_focus":  "흉터·모공",
  "device_id":      "d_xxxx (익명)",
  "feedback_id":    "uuid",
  "received_at":    "2026-06-03T07:49:08Z"
}
```

---

## 6. 충분성 검토 — 지금 당장 가능한 분석

| 질문 | 사용 변수 | 가능 여부 |
|---|---|---|
| 20대 남성은 여름에 비염을 많이 검색하나? | age+gender+season+query | ✅ |
| PM2.5 나쁜 날 이비인후과 검색 증가? | pm25_bucket+standard_specialty | ✅ |
| 어떤 시간대에 어떤 진료과가 검색되나? | time_bucket+standard_specialty | ✅ |
| BMI 높은 사람이 정형외과를 많이 찾나? | bmi_bucket+standard_specialty | ✅ |
| 클릭 → 상세 진입 전환율이 높은 병원은? | click+select+hospital_id | ✅ |
| 피드백이 높은 병원의 공통점은? | agree_ratio+standard_specialty | ✅ |
| 여름 더위에 피부과 vs 이비인후과 비율? | temp_bucket+standard_specialty | ✅ |
| 일교차 큰 날 감기 검색 급증? | temp_diff_bucket+query | ✅ |
| 꽃가루 시즌 알레르기 검색 패턴? | pollen_bucket+query | ❌ (미연동) |

---

## 7. 환경 신호 수집 현황

| 신호 | 버킷 | API | 상태 |
|---|---|---|---|
| 기온 | cold/cool/mild/warm/hot | 기상청 T1H | ✅ 수집 중 |
| 체감온도 | same | 기상청 기온 대체 | ✅ |
| 습도 | dry/normal/humid | 기상청 REH | ✅ 수집 중 |
| PM2.5 | good/moderate/bad/very_bad | 에어코리아 | ✅ 수집 중 |
| 계절 | spring/summer/fall/winter | 시스템 시각 | ✅ |
| 시간대 | dawn/morning/afternoon/evening | 시스템 시각 | ✅ |
| 요일 | weekday/weekend | 시스템 시각 | ✅ |
| 일교차 | small/normal/large/very_large | 기상청 단기예보 | ✅ 수집 중 |
| 꽃가루 | none/low/moderate/high/very_high | 질병관리청 | ❌ 미연동 |

---

## 8. 다음 작업 순서

### Next 1 — 배치 집계 + 인사이트 시각화

```
① be/scripts/compute_health_stats.py 작성 완료
   HEALTH_EVENT 전체 스캔 → 쿼리×계절×날씨×프로파일 그룹핑
   k-anonymity(k≥5) 적용 → STATS#INSIGHTS/LATEST 저장

② be/scripts/seed_demo_analytics_events.py 작성 완료
   데모 이벤트 생성 (다양한 조합)
   비염/탈모/무릎통증/여드름 × 여름/겨울 × 20~50대 × 날씨 조합

③ /insights FE 페이지 추가 완료
   검색어별 계절 분포 바 차트
   연령·성별 분포
   날씨별 검색 패턴
```

실행:

```bash
python -m be.scripts.seed_demo_analytics_events --count 180
python -m be.scripts.compute_health_stats
```

API:

```text
GET /api/analytics/insights
GET /api/analytics/insights?refresh=true
```

### Next 2 — CTR/SCR → 검색 랭킹 반영

```
compute_event_scores.py 이미 계산 중 (EVENT#STATS)
be/api/search.py 에서 읽어서 relevance_score에 가중치 추가
→ 많이 클릭된 병원이 자연스럽게 상위 노출
```

### Next 3 — 데이터 품질 개선

```
query 빈 문자열 → null 처리
날씨 unknown 이벤트 비율 감소 (현재 942건 중 20건만 채워짐)
```

---

## 9. DynamoDB 테이블 전체 구조

### kmuproj-02-team3-backend (Main — 기존 BE)

```
META / CLASSIFICATION / DESCRIPTION / SERVICES / RELATED
SITE#PAGES / SITE#IMAGES
NAVER#PLACE / NAVER#PLACE#REVIEWS / NAVER#BLOG
KAKAO#PLACE / KAKAO#REVIEWS / KAKAO#BLOG
GOOGLE#PLACE
PUBLIC#DEVICES / PUBLIC#DOCTORS
VISION#RESULTS / INGEST#STATE
FEEDBACK#{id}   ← 피드백 (BE + FE 연결 완료)
HISTORY#{iso}   ← 분류 변경 이력
EVENT#{type}#{ts} ← 기존 이벤트
EVENT#STATS       ← CTR/SCR 집계

GSI: sigungu-specialty-index / geo-index
```

### kmuproj-02-clinic-Analytics (신규 — 데이터 해자 전용)

```
EVENT#{device_hash} / EVENT#{type}#{ts}   ← HEALTH_EVENT (수집 중 942건)
PROFILE#{device_hash} / PROFILE           ← 건강 프로파일 (opt-in)
STATS#QUERY#{검색어} / STATS              ← 검색어별 집계 결과
STATS#INSIGHTS / LATEST                   ← /insights 최신 운영 대시보드

특징:
  TTL = 1년 (raw 이벤트 자동 만료)
  Main 테이블과 완전 분리 — 충돌 없음
  device_id는 SHA-256 해시 16자리로 저장
```

---

## 10. 검색 랭킹 구조

```
relevance_score = max_chunk_cosine              (의미 관련성 게이트)
               + W_PF    · [primary_focus 일치] (주력 주장 여부)
               + W_FREQ  · log1p(언급 횟수)     (언급 빈도)
               + W_CHUNK · log1p(청크 수−1)     (사례 폭)
               + W_CTR   · log1p(ctr)           ← 다음 단계 추가 예정
               + W_SCR   · log1p(scr)           ← 다음 단계 추가 예정

검색 시점 LLM: 0회 | 응답시간: ~200ms | 검색당 비용: ~$0.00003
```

A/B 검증 (강남 전수): P@1 0.571→0.655 / P@5 0.562→0.617 / MRR 0.675→0.734

---

## 11. 추후 개발

```
공공 보건 트리거 (질병관리청 독감 유행 단계, 식중독 주의보)
꽃가루 지수 연동 (질병관리청 API)
검색 세션 연계 (같은 세션 내 증상 → 진료과 흐름)
지역 의료 공백 지수 (수요/공급 비율 → B2B 보고서)
```

---

## 12. 신규 환경변수 (.env)

```
ANALYTICS_TABLE=kmuproj-02-clinic-Analytics
KMAS_API_KEY=...       기상청 초단기실황 (data.go.kr, 활성화됨)
AIRKOREA_API_KEY=...   에어코리아 PM2.5 (data.go.kr, 동일 키, 활성화됨)
```

---

## 13. 제약

- **main 직접 수정 금지** — 모든 작업 feature 브랜치
- **검색 시점 LLM 0회** — 자연어=KB Retrieve / 카테고리=DDB GSI / 위치=haversine
- **의료법 §56 주체 명시** — "이 병원이 자기 사이트에서 ~를 표시함", 평가·추천 금지
- **LLM/Vision 추가 호출 동결** — 개인계정 쿼터 소진 (2026-06-01~)
- **KB delete 금지** — soft-delete(`status=closed`)만
- **신체 조건 원본 서버 미전송** — BMI 계산은 FE에서만, 버킷값만 BE 전달
- **k-anonymity k≥5** — 집계 시 그룹 인원 5 미만 셀 제거
- **opt-in 기본값** — 건강 프로파일 미입력이 default
- **Event 실패는 UX 차단 금지** — fire-and-forget
