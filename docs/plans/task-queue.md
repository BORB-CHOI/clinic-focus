# clinic-focus 작업 큐 — V2 완전 서비스

> 최종 업데이트: 2026-05-28 · 상위 컨텍스트: [`../overview.md`](../overview.md), [`../dev-roadmap.md`](../dev-roadmap.md)
>
> 연관 문서: 완료 작업 누적 → [`done-catalog.md`](done-catalog.md) · 네이버·카카오 크롤 실측 raw → [`external-crawl-findings-2026-05-28.md`](external-crawl-findings-2026-05-28.md) · 분류 스키마 근거 → [`specialty-schema-analysis-2026-05-27.md`](specialty-schema-analysis-2026-05-27.md)

이 문서는 **clinic-focus 가 완전한 서비스(9가지 차별점 전부 진짜로 동작)** 가 되기까지 남은 작업을 한 곳에 묶은 단일 큐다. PoC 시연 수준이 아니라 *기획안에 적힌 본 서비스가 가동되는 상태*가 V2 정의.

---

## 0. V2 정의 — 완전 서비스

**완전 = 다음 다 동작**:

1. 4개 외부 소스 모두 크롤링·DDB 적재·임베딩까지 통과 (자체 사이트 / 네이버 플레이스+블로그 / 카카오맵 / 구글 Places)
2. KB ingest 본문이 4 시그널 다 포함 → 자연어 검색이 사용자 표현(블로그·후기 어조)과 매칭
3. AI 자연어 통합 설명이 4 시그널 다 인용 + 출처 배지 부착
4. FE 상세 페이지 9개 영역 전부 진짜 데이터로 렌더
5. 피드백 1-tap → DDB 적재 → 임계 도달 시 신뢰도 재계산 → 변경 이력 자동 기록
6. 표본: 강남 4과목 88개 → 서울 5개구 1만 풀커버 (단, **AI 시그널은 표본 분할**, 아래 §0-1)

PoC 시연(14개) 은 통과한 상태(PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25)). 본 큐는 그 위에 "본 서비스" 까지 가는 모든 작업.

### 0-1. 표본 분할 — AI 시그널 비용 통제

**비용 폭증 위험 시그널은 시연 10개 한정. 룰·외부 API 시그널만 1만 풀커버.**

| 처리 | 표본 | 모델·소스 | 비용 형태 | 근거 |
|---|---|---|---|---|
| HIRA 메타 적재 | **1만** (서울 5개구) | 공공 API | 무료 | 콜드 스타트 보강 |
| 자체 사이트 크롤링 | **1만** | httpx + BS4 | HTTP 호출만, 비용 0 | — |
| 룰 기반 자칭 분류 (트랙 A) | **1만** | 키워드/빈도 룰 | LLM 미사용, 비용 0 | 베이스라인 |
| 네이버 검색 API (블로그) | **1만** | 네이버 검색 API | 무료 25,000건/일 — 가능 | 4 시그널 中 블로그 |
| 네이버 플레이스 + 카카오 + 구글 리뷰 | **1만** | 각 외부 API | 카카오·네이버 무료 / 구글 Places ~$170 | 4 시그널 中 후기 |
| 심평원 의료기기·의사 신고 | **1만** | 공공 API | 무료 | 영역 ② · ③ |
| **LLM 텍스트 분류 (트랙 B)** | **10개** | Bedrock Haiku 4.5 | $0.05~0.20/병원 | 지원 계정 한도 + 룰 기반과 비교 시연 |
| **LLM `generate_description`** | **10개** | Bedrock Haiku 4.5 (개인 계정 ap-northeast-2) | LLM 호출 — 시연 한정 | 9990개는 `ai_description=null` (FE 차등 렌더링) |
| **Vision 분석 (트랙 C)** | **10개** | Sonnet 4.6 (개인 계정) | $0.012/이미지 × `MAX_VISION_IMAGES=10` | Marketplace 구독 후 활성, 시연 한정 |
| **임베딩 (Titan v2)** | **1만** | KB 자동 호출 | $0.00003/문서, ~$0.30/1만 | 자연어 검색 전 표본 매칭 |
| **KB ingest 본문 합성** | **1만** | 본문 조립 로직 | 무료 | 단 LLM 설명은 10개만 박힘, 나머지는 룰 결과로 본문 구성 |

**결론**: 1만 풀커버에 들어가는 비용은 ~$170 (구글 Places) + ~$0.30 (임베딩) + 외부 API 무료 + EC2 가동. LLM·Vision 호출만 시연 10개로 묶어 비용 통제. FE 상세 페이지는 `ai_description == null` 차등 렌더링으로 9990개도 룰 기반 태그 카드 + 4 시그널 통계가 채워진다.

---

## 1. V2 매트릭스 — 9가지 차별점 vs 현 상태 (확장)

| # | 기능 | 외부 데이터 의존 | 현 상태 | 차이 |
|---|---|---|---|---|
> **현 상태 = 코드 정합 기준** (2026-05-28 전수 검사). 대부분 코드는 완성됐고
> 남은 차이는 **실데이터(외부 크롤·KB ingest)·FE(Phase E)·Vision Marketplace** 의존.
> "코드 완성"은 단위 테스트 통과 기준이며 실데이터 e2e 는 미검증.

| # | 기능 | 외부 데이터 의존 | 현 상태 | 남은 차이 |
|---|---|---|---|---|
| 1 | 자연어 검색 (KB Retrieve) | 4 시그널 본문이 KB ingest 에 다 들어가야 진짜 매칭 | △ 코드 완성 (`retrieve_hospital` + 시그널별 청크 빌더 `build_signal_chunks`) | 실데이터 KB ingest 후 검증 (외부 크롤 → ingest 일괄) |
| 2 | 상세 페이지 9개 영역 | 모든 영역의 데이터 소스가 채워져야 | △ BE 9영역 join 완성 (`be/api/hospital.py`) | FE 컴포넌트 미구현(Phase E) + 실데이터 |
| 3 | AI 통합 설명 | 4 시그널 다 받아야 종합 가능 | ✅ 코드 완성 (`generate_description` 4 시그널 `detailed_signals` 종합 + citations 강제) | 시연 10개 실호출 (Phase F) |
| 4 | 4 시그널 교차 검증 | Vision + 블로그 + 후기 다 켜져야 | △ 코드 통합 완성 (자칭·블로그·후기 + 카카오/네이버/구글, 도배 페널티) | Vision 만 Marketplace 대기 + 후기 실데이터 |
| 5 | 신뢰도·피드백 자기교정 | Feedback 누적 + 임계 + 재계산 | ✅ 코드 완성 (`recompute_confidence`·`aggregate_feedback_stats` + feedback API inline 연동) | 실피드백 누적 후 동작 확인 |
| 6 | 분류 변경 이력 자동 기록 | 재분류 시 diff + HISTORY# INSERT | ✅ 코드 완성 (`_record_classification_change`, primary_focus diff 시 자동) | 재크롤·재분류 e2e |
| 7 | 피드백 (디바이스ID 중복방지) | API + UI + DDB | △ API 완성 (`POST /api/feedback`, device_id+hospital_id 409) | FE UI 미구현(Phase E) |
| 8 | 관련 병원 추천 | 유사도 + 메타필터 + "다루지 않는 분야 대안" | ✅ 코드 완성 (`find_related_hospitals` same_focus/fills_gap + `alternative_hospital_ids` in-place) | 실데이터는 KB ingest 후 |
| 9 | 카테고리 이중 색인 | extract 실측 + "다루지 않는 분야" 정확도 | △ 코드 완성 (`extract_services_and_doctors`) | 실측 정확도 검증(Phase F) |

---

## 2. 빠진 외부 데이터 소스 (네 트랙)

본 서비스 4 시그널은 *자체 사이트만으로 못 채워진다*. 외부 3개 소스가 들어와야 비로소 4 시그널 완성.

| 시그널 | 가중치 | 데이터 소스 | API/방법 | 키 발급 | 현재 |
|---|---|---|---|---|---|
| 자칭 | 25% | 의료기관 자체 사이트 | httpx + BS4 (있음) | — | ✅ 14개 |
| Vision | 30% | 자체 사이트 이미지 (시술·기기 사진) | Bedrock Sonnet 4.6 | 개인 계정 Marketplace 구독 | ❌ fallback 중 |
| 블로그 | 20% | 네이버 블로그 검색 (`{병원명} {지역}`) | 네이버 검색 API (`v1/search/blog`) | 네이버 개발자센터 | ❌ |
| 후기 | 25% | 네이버 플레이스 + 카카오맵 + 구글 Places 리뷰 | (1) 네이버 플레이스 (비공식 GraphQL/스크래핑) (2) 카카오 로컬 API + 카카오맵 리뷰 (3) Google Places API `reviews` 필드 | 카카오·구글 Places | ❌ |

보조 출처 (시그널엔 안 들어가지만 9영역 데이터로 활용):
- 영업시간·전화·주차 → 네이버 플레이스 / 카카오 로컬 API (현재 `kakao_adapter.py` 일부 있음)
- 좌표 → 카카오 좌표 변환 (있음) / HIRA (있음)
- 사진 (외관·인테리어) → 네이버 플레이스
- 의료기기 신고 → 심평원 공공 API (이미 있음)

---

## 3. DDB 재설계 — single-table 통일

**현재 모순**: BE 실 운영 = single-table(`kmuproj-02-team3-backend`, PK=`hospital_id`+SK=`entity`, 3124 items). AI 트랙 코드 = 7-table 가정. 4 시그널 다 켜면 entity 종류 폭증 — 7-table 로는 관리 안 됨. **AI 도 single-table 로 재설계**.

### 3-1. 단일 테이블 스키마

테이블 이름: `kmuproj-XX-clinic-{Hospitals|Main}` (이름은 마이그레이션 시 결정).
PK = `hospital_id` (S)
SK = `entity` (S)

### 3-2. entity 종류

| SK 값 | 내용 | 시그널 | 출처 |
|---|---|---|---|
| `META` | 이름·주소·위경도·시도·시군구·전화·표준 진료과목·website_url | — | HIRA + 카카오 |
| `SITE#PAGES` | 자체 사이트 크롤링 결과 (`CrawlData.pages[*]`) | 자칭 | 자체 사이트 |
| `SITE#IMAGES` | 자체 사이트 이미지 메타·URL | Vision | 자체 사이트 |
| `NAVER#PLACE` | 네이버 플레이스 정보 (영업시간·전화·사진 URL·총 방문자 수 등) | 후기 보조 | 네이버 |
| `NAVER#PLACE#REVIEWS` | 네이버 플레이스 방문자 리뷰 키워드 빈도 | 후기 | 네이버 |
| `NAVER#BLOG` | 네이버 블로그 검색 결과 + 본문 추출 (상위 N개) | 블로그 | 네이버 |
| `KAKAO#PLACE` | 카카오 로컬 API 장소 정보 | 후기 보조 | 카카오 |
| `KAKAO#REVIEWS` | 카카오맵 리뷰 키워드 빈도 | 후기 | 카카오 |
| `GOOGLE#PLACE` | Google Places `place_id` + 기본 정보 | 후기 보조 | 구글 |
| `GOOGLE#REVIEWS` | Google Places 리뷰 키워드 빈도 | 후기 | 구글 |
| `PUBLIC#DEVICES` | 심평원 의료기기 신고 목록 | 기기 | 심평원 |
| `PUBLIC#DOCTORS` | 심평원 의료진 전문의 자격 | 의료진 | 심평원 |
| `VISION#RESULTS` | Vision 이미지 분류 결과 (시술·기기 식별) | Vision | Bedrock |
| `CLASSIFICATION` | `Classification` (standard_specialty·primary_focus·confidence·signals) | — | AI |
| `DESCRIPTION` | `HospitalDescription` (headline·paragraphs·citations·generator_model) | — | AI |
| `SERVICES` | `ServicesAndDoctors` (services·excluded_services·equipment·prices·doctors) | — | AI |
| `RELATED` | `find_related_hospitals` 결과 (same_focus·gap_fill) | — | AI |
| `INGEST#STATE` | `content_hash` · `last_ingested_at` · `kb_data_source_object_key` (hash diff 용) | — | AI |
| `FEEDBACK#{device_id}#{timestamp}` | 1-tap 피드백 1건 (verdict·primary_focus 평가 대상) | — | FE |
| `FEEDBACK#STATS` | 집계 (total/agree/disagree/agree_ratio/last_feedback_at) | — | AI 갱신 |
| `HISTORY#{changed_at_iso}` | 분류 변경 이력 1건 (from_focus→to_focus·reason·signal_source) | — | AI 자동 |

### 3-3. GSI

| GSI | PK | SK | 용도 |
|---|---|---|---|
| `sigungu-specialty-index` | `sigungu#standard_specialty` (META 항목만) | `confidence_score` (Number, 내림차순) | 카테고리 탐색 (BE 직접 조회, AI 미경유) |
| `geo-index` | `geohash_prefix` (META 항목만) | `lat#lng` | 지도 근처 검색 (필요 시) |

---

## 4. V2 sprint — 단계별 잔여 작업

### Phase A — 기반 재설계 (다른 모든 단계의 차단 요인)

- [x] `shared/models.py` 4 시그널 다 받도록 확장 (외부 시그널 소스 모델 완료, 2026-05-28)
  - [x] 신규 모델: `KakaoPlace`·`KakaoReviews`·`KakaoBlog`·`KakaoReviewItem`·`KakaoBlogSeed`·`KakaoHira`·`KakaoCategory`·`NaverPlace`·`GoogleReviews`·`GoogleReviewItem`·`ExternalSignalBundle` (모두 `extra="ignore"` — parse_* 향후 필드 방어, PII 필드 없음)
  - [x] `Classification.signals`(=`DetailedSignals`) 는 이미 `self_claim`·`vision`·`blog`·`reviews` 보유 — 추가 작업 불필요(확인 완료, 옛 설명 정리)
  - [x] `NaverBlogPost`·`ExternalCrawlData`·`HospitalIngestMetadata` 는 **만들지 않기로 확정** (2026-05-28) — 외부 합본은 `ExternalSignalBundle` 로 충분(단 classify/build_signal_chunks 는 개별 인자로 받음). ingest 메타는 모델 없이 `build_ingest_metadata` 가 평탄 dict 반환(KB 가 평탄 dict + 빈리스트/None 거절을 요구 — 모델 끼우면 변환 레이어 중복). `signals_included`·`last_updated` 같은 표시용 값은 KB metadata 가 아니라 DDB `CLASSIFICATION`/`INGEST#STATE` 에서 9영역이 직접 읽음
- [x] **DDB 단일 테이블 마이그레이션** (Phase A 1차, 2026-05-27, PR [#28](https://github.com/BORB-CHOI/clinic-focus/pull/28))
  - [x] `be/adapters/dynamo_adapter.py` 전면 재작성 — 7개 테이블 메서드를 entity SK 기반 단일 어댑터로 (`get_entity`/`put_entity`/`query_hospital_entities`/`iter_all_hospital_ids` 등 generic primitives + typed helper 유지)
  - [x] AI/BE 양쪽 `dynamodb.Table("Hospitals")` 류 호출을 새 어댑터 메서드로 교체 (`ai/scratch/kb_ingest.py` 한 곳)
  - [x] 옛 7-table 폐기 (콘솔 수동 삭제, AI 트랙 14개 데이터 폐기 — 이관 안 함)
  - [x] **신규 V2 단일 테이블 콘솔 수동 생성 완료** — `kmuproj-10-clinic-Main` ACTIVE 확인(2026-05-28), GSI 2개(`sigungu-specialty-index`·`geo-index`) 생성됨. DynamoAdapter read/write 연결 동작 확인(현재 item 0 = 데이터 적재 전)
  - [ ] 검증: BE 크롤링 1만 데이터 받은 후 자연어 검색 4쿼리 회귀 (데이터 적재 후)
- [x] **BE → AI S3 크롤링 데이터 1차 mirror** (2026-05-27)
  - [x] BE 가 강남 502개 (`crawl/{hospital_id}/crawl_data.json` 평탄 구조, ~21MB) 를 사용자에게 tarball 전달
  - [x] AI 버킷 `kmuproj-10-clinic-focus-crawl/crawl/` 에 sync 완료
  - [x] Pydantic `CrawlData` 검증 통과 (샘플 1건, pages=10/images=30)
  - [ ] **장기 — BE 가 PutObject 시점에 양쪽 버킷에 mirror 자동화 (옵션 A)** — BE 협조 필요. 풀커버(1만) 진입 전 합의
- [x] **분류 스키마 확장 — V2 풀커버 진입 차단 해제** (2026-05-27)
  - 강남 502개 S3 mirror + HIRA 종별 분포 + 의원 99개 본문 키워드 매칭 + 민간 3사(NHIS·닥터나우·굿닥·모두닥) 분류 체계 비교
  - 결론: `standard_specialty` 22 후보군 확정 (양방 16 + 한의원·치과 평탄화 2 + 종합·요양·보건소·기타 4). 표본 약 94% 커버
  - `primary_focus` 는 자율(`list[str]` 자유 문자열) 유지 — 룰 기반 분류기가 본문에서 자유 추출
  - `ai/CLAUDE.md` "분류 스키마" 박스 갱신 + 분석 노트 [`ai/scratch/specialty-schema-analysis-2026-05-27.md`](../../ai/scratch/specialty-schema-analysis-2026-05-27.md) 박음
  - **후속**: BE 담당자에 22 후보군 공유 + GSI `sigungu_specialty` 검증 추가 요청 / FE 검색 필터 옵션 22개로 갱신 / `be/adapters/hira_adapter.py` `_get_specialists` 정정 (현 `getHospBasisList` 호출은 `dgsbjtCdNm` 필드가 응답에 없어 항상 빈 리스트 반환)
- [x] 외부 API 키 발급 — **완료** (2026-05-28 `.env` 실측 확인, 사용자 트랙)
  - [x] `.env.example` 에 신규 키 변수 + 코멘트 (`KAKAO_REST_API_KEY`·`NAVER_MAP_*`·`GOOGLE_PLACES_API_KEY`·`BEDROCK_VISION_MODEL_ID`)
  - [x] 카카오 로컬 API 키 / 구글 Places 키 — `.env` 설정됨 (32자 / 39자)
  - [x] 네이버 검색 API — `NAVER_MAP_CLIENT_ID`·`NAVER_MAP_CLIENT_SECRET` `.env` 설정됨. **변수명만 `_MAP` 이고 실제로는 `openapi.naver.com` 검색 API 키**(NCP Maps 아님, `.env.example` 주석 명시). 하나의 키로 블로그(`v1/search/blog`)·지역 검색 다 호출 — 추가 키 불필요
  - [x] 개인 AWS 계정 Bedrock Sonnet 4.6 (Vision) — `global.anthropic.claude-sonnet-4-6` 실호출 성공 확인(2026-05-28, ap-northeast-2). 구독·자격증명 정상
- [x] BE 본체 차단 이슈 머지 (2026-05-28)
  - [x] 이슈 [#23](https://github.com/BORB-CHOI/clinic-focus/issues/23) `s3_adapter` boto3 (이미 전환됨) + `crawl_all.py` 옛 `Table("Hospitals")` 직접 scan → `DynamoAdapter.iter_hospitals_with_url()` 로 V2 single-table 정합
  - [x] 이슈 [#24](https://github.com/BORB-CHOI/clinic-focus/issues/24) `load_env` 인라인 주석 버그 — `_strip_inline_comment` 로 ` # comment` 절단(값 안 `#` 보존)

### Phase B — 외부 시그널 크롤러 4종 (BE)

> **실측 raw 노트 이전됨** — 네이버·카카오 플레이스 비공식 엔드포인트 실측(robots/약관 ·
> GraphQL 스키마 · PII · 운영비용 · 사실 1~24)과 Vision 입력 전략은
> [`external-crawl-findings-2026-05-28.md`](external-crawl-findings-2026-05-28.md) 로 분리. 핵심 결정 요약:
>
> - **Vision 입력 = 병원 자체 사이트 한정** (외부 플랫폼 사진은 FE 대표 이미지로만, Vision 분석 입력 제외 — 자칭 시그널 오염 방지)
> - **네이버·카카오 후기/정보 탭 수집은 회색지대** (robots Disallow + 약관 자동화 금지) → 실제 크롤 실행은 운영자 결정. 구글 Places·네이버 블로그 공식 API 는 합법
> - 카카오 panel3 1회 = 네이버 3 호출분 회수(풀커버 호출비용 ⅓), 단 둘 다 검색 매칭 실패율 ~40% (정확한 병원명+지역 필요)
> - 후기 본문 raw 는 §56③ 상 DDB 저장·임베딩 입력만 허용, 화면 노출은 키워드 빈도만

- [x] `be/core/crawler.py` HTML 잡음 정제 (이슈 [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13), 2026-05-28)
  - [x] `_denoise_pages` — 페이지 간 반복 단락 검출(전체 70%+ 등장 = 푸터/메뉴, 페이지<3 스킵, 전부 날아가면 블랙리스트만 fallback)
  - [x] 잡음 블랙리스트(개인정보취급방침·환자권리장전·이용약관·404·Copyright·modoo·사업자등록번호). **비급여는 제외 — 시술명·가격(PriceItem) 원천이라 시그널**
  - [x] 정제 후 100자 미만 → "[정보 부족]" 마크
- [~] 네이버 플레이스 — **어댑터 완성, 크롤 실행만 남음** (2026-05-28)
  - [x] `be/adapters/naver_place_adapter.py` — Playwright headless 로 ncpt 토큰 자동 발급 → `pcmap-api.place.naver.com/graphql`(getVisitorReviews) fetch + 순수 파서 `parse_place`. 후기 본문(body) 보존, 작성자 PII(author·userIdno·nickname) 미보존. GraphQL 쿼리 `be/adapters/naver_queries/`. classify `_analyze_reviews` + primary_topics 에 후기 본문 합류(키워드 빈도는 AI 자체 추출 — 네이버는 병원 카테고리 통계 미제공, 사실 8)
  - [ ] 실제 크롤 실행 → `NAVER#PLACE#REVIEWS` 적재 (회색지대 — 운영자 결정, Playwright 1건 18~25초)
- [x] 네이버 블로그 — **어댑터 완성** (2026-05-28)
  - [x] `be/adapters/naver_blog_adapter.py` — 공식 `v1/search/blog`(NAVER_MAP_* 키 = 검색 API 키) httpx 단발 + `parse_naver_blog`(HTML 태그·엔티티 제거, 작성자 PII 미보존). classify `_analyze_blog(_rule)` + kb_store `build_blog_chunk` 에 posts title+description 합류
  - [ ] 실제 크롤 실행 → `NAVER#BLOG` 적재 (공식 API, 합법. 외부 크롤 일괄 시점)
- [~] 카카오 — **어댑터 완성, 크롤 실행만 남음** (2026-05-28, 커밋 `9d0f256`·`7d79ab8`)
  - [x] 비공식 실측 완료 — 공식 `dapi.kakao.com` 으로 place_id 획득 → `place-api.map.kakao.com` panel3/reviews/blog httpx 단발(ncpt·Playwright 불필요). 사실 13~24
  - [x] `be/adapters/kakao_place_adapter.py` — fetch + 순수 파서(parse_place/reviews/blog) + PII 제거 + place_id 검증. AI `build_signal_chunks` 가 소비할 형태(tags·키워드 빈도·블로그 시드)
  - [ ] 실제 크롤 실행 → `KAKAO#PLACE`/`KAKAO#REVIEWS` DDB 적재 (외부 크롤 일괄 시점)
- [~] 구글 — **어댑터 완성, 크롤 실행만 남음** (2026-05-28)
  - [x] `be/adapters/google_places_adapter.py` — Places API (New) Text Search → Details(`reviews` 5건 한정, FieldMask) + 순수 파서 `parse_google_reviews` + `to_google_reviews` 모델 승격. 작성자(authorAttribution)·사진·절대시각 PII 미보존. 공식 API 라 합법
  - [ ] 1만에 실제 크롤 실행 → `GOOGLE#PLACE` entity 적재 (외부 크롤 일괄 시점). 키워드 빈도는 AI 트랙이 후기 본문에서 자체 추출 (구글은 strength 미제공)
- [~] `be/scripts/crawl_external_all.py` — **골격 완료, 실행 미실행** (2026-05-28)
  - [x] 병원당 카카오(공식 dapi→place_id→place-api panel3/reviews/blog) + 구글(Text Search→Details) fetch→parse→DDB(`KAKAO#*`/`GOOGLE#PLACE`) 적재 골격. **기본 dry-run** (`--confirm` 없으면 네트워크 0건), `--source google` 로 합법 범위 한정, 카카오 포함 시 회색지대 경고 출력. 주소 누락 병원 스킵
  - [ ] **실제 1,084 실행은 사용자(운영자) 결정** — 카카오 회색지대(robots/약관) + 1만 rate-limit 미실측. 구글만이면 합법
- [ ] **hash diff 기반 부분 재처리** (이슈 [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13) 후반부)
  - 각 entity 에 `content_hash` 컬럼 추가
  - 재크롤링 시 hash 동일하면 KB 재 ingest 스킵
- [ ] 의료법 후기 처리 룰 — 리뷰 본문 raw 는 DDB 저장 + **임베딩·AI 자연어 설명 생성 입력으로만 사용** (KB ingest 본문에 포함 가능). 화면 노출은 **키워드 빈도·태그·`visitCategories` 만** — 개별 후기 본문 직접 노출 절대 금지

### Phase C — AI 본체화 + 4 시그널 통합

> ✅ **결정 (2026-05-28, 사용자) — 임베딩·분류·설명 파이프라인 입력·시점**
>
> 세 산출물(CLASSIFICATION·임베딩 청크·DESCRIPTION)의 입력·실행 시점·범위·임베딩 관계를 분리해 못박는다. 배경: 현재 `index_hospital` 은 **병원당 벡터 1개**(청킹 없음)에 **DESCRIPTION 합본**을 임베딩 → 두 문제. ① 커버리지 — DESCRIPTION 이 시연 10개뿐이라 자연어 검색이 10개만 본다. ② 희석 — 4 시그널을 한 벡터에 합치면 강한 의료 신호가 잡신호(주차·친절·광고)와 평균돼 정확도 하락(데이터 많은 병원이 역설적으로 불리). **Titan 임베딩은 10개 제한이 없고 전체 자유**(§0-1)이므로, 검색 임베딩을 LLM(DESCRIPTION, 10개 한정)에 묶지 않고 **정제 원본 시그널 청크**로 전환해 풀커버한다.
>
> | 산출물 | 입력 | 실행 시점·범위 | 저장 | 임베딩 관계 |
> |---|---|---|---|---|
> | **CLASSIFICATION** (태깅·신뢰도) | 4 시그널(자칭 키워드·공공 진료과목/HIRA·블로그·후기 빈도) + 심평원 META | ingest **전**, **전체 1만** (룰 기반·LLM 없음·공짜) | DDB `CLASSIFICATION` + `META` GSI 키 | **연결** — 청크 metadata(`standard_specialty`·`primary_focus`·`confidence_score`·`sigungu`·`lat`/`lng`) 공급 |
> | **임베딩 청크** | **정제 원본 시그널 텍스트**(시그널별 분리) | CLASSIFICATION **직후**, **전체 1만** (Titan·공짜) | 벡터 S3 (KB 경유) | **본체** — DESCRIPTION 아님 |
> | **DESCRIPTION** (LLM 설명문) | 4 시그널 + CLASSIFICATION 결과 | **시연 10개만** (Haiku/Nova·비용 한정) | DDB `DESCRIPTION` | **분리** — 벡터 미포함, 상세페이지 표시용 |
>
> **청킹 전략**: 병원당 벡터 1개 ❌ → **시그널별 청크**(자칭/Vision/블로그/후기)로 분리, 각 청크에 `signal_type` + 위 CLASSIFICATION 메타 부착. KB ingest 시 한 병원을 **시그널별 문서로 나눠** 올려 signal 경계 유지(KB 크기 자동청킹은 각 문서 안에서만 동작 — 합본 1문서로 올리면 시그널 경계가 크기로 잘림). 쿼리는 가장 가까운 청크가 매칭 → 잡신호 청크는 안 걸리고 관련 청크만, "왜 걸렸나" 추적 가능.
>
> **정확도 방어 (이미 구현)**: `_build_meta_filter` 의 구·과목 필터 + `confidence_score ≥ 70` 게이팅 + 신뢰도 정렬 → 총망라(recall)로 가도 지리·과목·저신뢰 오매칭은 메타필터/재랭킹이 정리(precision). recall = 원본 청크, precision = 필터/재랭킹 역할분담.
>
> **의료법 §56③**: 후기·블로그 raw 는 임베딩 **입력**으로 허용(저장·임베딩 OK). 단 **검색 결과 화면에 매칭된 raw 청크(후기 본문·광고 문구) 노출 금지** — 이름·주력 태그·신뢰도 정제 필드만 표시.
>
> **표준 진료과목 보너스**: `standard_specialty` 는 심평원 공공데이터(HIRA 진료과목)로 상당 부분 채워져 LLM 없이도 메타필터 키 확보 가능.
>
> → 이 결정이 아래 `ingest_hospital` 본문 구성 항목의 "[AI 분류 결과·설명]" 포함 가정을 **갱신**: DESCRIPTION 은 임베딩 본문에서 **분리**하고, 임베딩 본문 = 시그널 원본 청크. CLASSIFICATION 결과는 본문이 아니라 **metadata** 로만 들어간다.
>
> ---

- [x] **`ai/search/kb_store.py` 신규 — KB 경유 ingest/retrieve** (2026-05-28, 커밋 `665c496`·`cb502bb`)
  - [x] `ingest_hospital(hospital_id, signal_chunks: dict[str,str], metadata, *, trigger_ingestion=False)` — 시그널별 `{id}/{signal_type}.txt` + metadata 사이드카 KB 적재. 청크 빌더(`build_signal_chunks`·`build_ingest_metadata`)는 호출자가 조립
  - [x] `retrieve_hospital(query) -> list[SearchResult]` — KB Retrieve, team_id 필터 + 메타필터 + hospital_id dedup
  - [x] `ai/__init__.py` export: `ingest_hospital`·`retrieve_hospital` 추가, `index_hospital`·`search_similar` 제거. 옛 `ai/search/vector_store.py`(S3 Vectors 직접) 삭제
  - [x] 시그널별 청크 결정 적용 — CLASSIFICATION 은 metadata 로만, DESCRIPTION 임베딩 미포함, 빈 시그널 제외, 후기 청크는 키워드 빈도만(§56③)
  - [ ] `ai/scratch/` 폴더 삭제 (probe·레퍼런스 보존 중 — 본체 안정화 후)
  - [x] 카카오/네이버/구글 시그널을 `build_signal_chunks` 에 연결 (2026-05-28) — `build_*_chunk` 가 dict·Pydantic 모델 양받(`_as_dict` 정규화), `google_reviews` 인자 추가. 핸들러가 `db.load_external_signals` 로 DDB entity 로드해 `**external` 전개. 실데이터는 외부 크롤 DDB 적재 후 채워짐
- [~] **`classify_hospital` 룰 경로 추가** (2026-05-28, 커밋 `ad26f37`·`f4804d0`)
  - [x] `use_llm=False` 룰 단독 경로 — 자칭·블로그 키워드 룰 추출, Bedrock/Vision 0회, 전체 1만 적용. 룰 단독 신뢰도 상한 70 cap
  - [x] 자칭 도배 페널티·교차 검증·표준과목 추론은 기존 룰 로직 재사용
  - [x] 외부 시그널(카카오·네이버·구글) 통합 (2026-05-28) — `classify_hospital(..., kakao_place=, kakao_reviews=, kakao_blog=, naver_reviews=, google_reviews=)` 개별 인자(B안, `build_signal_chunks` 와 시그니처 일치). 카카오 `tags`→자칭 키워드/focus 보강(`_merge_kakao_tags_into_self_claim`, spam_score 는 사이트 기준 유지), 카카오/네이버/구글 후기→`_analyze_reviews` 실구현(키워드 빈도 합산 + 후기 본문에서 의료 키워드 추출해 primary_topics, §56③ 본문 미저장). 후기 채워지면 도배 페널티 `review_mismatch` 작동. dict·모델 양받. 테스트 25개 추가
  - [ ] `vision_results` 입력 통합 — Vision 본체(Marketplace) 활성화 후
- [x] **`generate_description` 4 시그널 종합** (본체 완성 — 2026-05-28 조사 확인)
  - `ai/prompts/hospital_description.md` 존재, 4 시그널(self_claim·vision·blog·reviews) 다 받음. `detailed_signals` 로 전달(외부 시그널은 classify 가 이미 흡수 — `external_signals` 파라미터 불필요, 명세 정합 완료)
  - citations 강제 검증(규칙 2 위반 시 에러) + 의료법 5규칙 프롬프트 강제 + 재시도(MAX_RETRIES=2)
- [ ] `ai/pipeline/vision.py` Vision **활성화** — 본체는 완성(analyze_images Bedrock Vision 호출·MAX_VISION_IMAGES 통제). **개인계정 Sonnet Marketplace 구독만 남음(사용자 트랙)**
- [x] `extract_services_and_doctors(...) -> ServicesAndDoctors` (본체 완성 — 조사 확인). services/excluded_services/equipment 추출, Vision+public_data 기기 중복 제거. `alternative_hospital_ids` 채움은 find_related 연결 시 보강 여지
- [x] `find_related_hospitals(...) -> list[RelatedHospital]` (본체 완성 — 조사 확인). same_focus(KB Retrieve+시군구)·fills_gap(excluded_services 순회)·haversine
- [x] `recompute_confidence(hospital_id, recent_feedback) -> Confidence` (2026-05-28 V2 single-table 정합) — 옛 7-table 직접 읽기 → `DYNAMO_TABLE` PK+SK(entity) get_item. 피드백 누적 임계·감점/보너스, confidence 만 조정(분류 유지). BE feedback API 가 inline 호출 연동
- [x] `aggregate_feedback_stats(hospital_id) -> FeedbackStats` (2026-05-28 V2 정합) — SK begins_with `FEEDBACK#`, `FEEDBACK#STATS` 집계 entity 제외
- [x] **분류 변경 자동 기록** (2026-05-28) — `index_hospital._record_classification_change`: 이전 `CLASSIFICATION` 과 primary_focus 다르면 `HISTORY#{changed_at}` 자동 INSERT(`save_change_record`). 최초 분류(prev=None)는 스킵. reason 기본 `scheduled_recrawl`
- [x] **Bedrock mock 의무화** — ai 단위 테스트 전부 `@patch("ai.core.bedrock_client.invoke_model")` 또는 boto3 mock. 실 호출 0

### Phase D — BE FastAPI 4개 엔드포인트 본체

- [x] `GET /api/search` ([API-FE-BE §1](../API-FE-BE.md#1-검색)) (2026-05-28 연동)
  - 자연어/위치: `ai.retrieve_hospital(SearchQuery)` → KB Retrieve. 시군구 단독: DDB GSI 직접(`category` 모드)
  - `_hospital_card` 가 META+CLASSIFICATION+DESCRIPTION join → 카드(standard_specialty·primary_focus·confidence·one_line_summary·matched_focus·distance_km)
  - `meta.total`·`search_mode`(natural/nearby/natural+nearby/category)·`query_interpretation` 채움. 실데이터는 KB ingest 후
- [x] `GET /api/hospitals/{id}` ([API-FE-BE §2](../API-FE-BE.md#2-병원-상세)) ⭐ (본체 완성 — 조사 확인). 9영역 DDB join + 404 + completeness
- [x] `GET /api/hospitals/{id}/history` ([API-FE-BE §3](../API-FE-BE.md#3-분류-변경-이력)) (본체 — `load_recent_changes`). 이제 분류 변경 자동 기록 연결돼 실데이터 채워짐
- [x] `POST /api/feedback` ([API-FE-BE §4](../API-FE-BE.md#4-피드백-제출)) (2026-05-28 연동) — verdict `Literal["agree","disagree"]`(오값 422), device_id+hospital_id 중복 409, 임계 도달 시 `recompute_confidence` inline 호출 → confidence 만 갱신(분류 유지), graceful(재계산 실패가 201 막지 않음)
- [~] `be/handlers/index_hospital.py` — `run_index_pipeline(hospital_id, *, demo=False)`. demo=False 룰 베이스라인, demo=True LLM/Vision. 외부 시그널 `**external` 전개 + 분류 변경 자동 기록 추가. 파일명 `ingest_hospital.py` rename 은 미적용
- [x] `be/handlers/api.py` CORS (2026-05-28) — env `CORS_ALLOW_ORIGINS`(쉼표 구분) 우선, 기본 `localhost:5173`. methods `GET,POST`. CloudFront 도메인은 Phase G 배포 시 env 주입
- [x] 응답 포맷 일관성 — `{"data",.."meta"}` / `{"error":{code,message}}` (4 엔드포인트 준수)
- [x] 표준 에러 코드 매핑 — `INVALID_PARAMETER` 400(422→400 정렬 완료), `NOT_FOUND` 404, `DUPLICATE_FEEDBACK` 409, `AI_SERVICE_ERROR` 502
- [ ] OpenAPI 자동 생성 검증 — FastAPI `/openapi.json` ↔ 명세 정합 (FE TS 타입 생성 시점에)

### Phase E — FE 9영역 + 4 시그널 시각화

- [ ] `openapi-typescript` 로 TS 타입 자동 생성 — `fe/src/types/api.ts`
- [ ] Mock 어댑터 (`fe/src/mocks/`) 제거 또는 dev 전용으로 분리
- [ ] `SearchPage.tsx` 실 API 연결
  - 자연어 입력 + 위치 토글 + 카카오맵 결합
  - TanStack Query `useSearch(q, filters)` 캐싱
  - 결과 카드: 표준 진료과목 + 실제 주력 + 신뢰도 + `one_line_summary` + 거리
  - 검색 결과 ↔ 지도 뷰 토글
- [ ] `HospitalDetailPage.tsx` 9개 영역 컴포넌트 — `fe/src/components/hospital/` 아래 분리
  - `HeadlineSection` — `ai_description` 자연어 단락 + 출처 배지 클릭→④ 스크롤
  - `CoreServicesSection` — services / excluded_services / equipment / prices
  - `DoctorsSection` — doctors 리스트 + 의사별 전공
  - `ConfidenceSection` — 신뢰도 게이지 + **4 시그널 기여도 분해 차트** + 펼침 메뉴 (자칭 원문·Vision 분포·블로그 토픽·후기 키워드)
  - `OperatingSection` — 주소(지도) + 전화(탭 가능) + 운영시간 + 야간/주말 + 주차 + 예약
  - `FeedbackSection` — 1-tap 👍/👎 (localStorage 디바이스ID) + 누적 통계 + 분류 오류 신고
  - `HistoryPreviewSection` — 최근 변경 1~2건 + 전체 이력 페이지 링크
  - `RelatedHospitalsSection` — same_focus 카드 + **"안 다루는 분야" gap_fill 카드 별도**
  - `MetaSection` — last_updated + data_sources + completeness 미만 시 경고 배너
- [ ] `ai_description == null` 차등 렌더링 — 태그 카드 fallback ([API-FE-BE §2](../API-FE-BE.md#2-병원-상세) 프론트 렌더링 가이드)
- [ ] `excluded_services[].alternative_hospital_ids` → ⑧ 영역 링크 (안 다루는 분야 옆에 "동네 대안: △△의원")
- [ ] `metadata.warning` 배너 / `data_completeness < 0.6` 시 빈 영역 "정보 부족" 표시
- [ ] 디바이스 ID 유틸 (`fe/src/lib/device.ts`) — localStorage `app_device_id` 키, 최초 방문 시 `crypto.randomUUID()` 생성
- [ ] **변경 이력 전체 페이지** (`/hospitals/{id}/history`) — `HistoryPreviewSection` 의 "전체 이력" 링크 도착지
- [ ] 카카오맵 SDK 마커 색상 — 신뢰도 등급(확실=초록 / 추정=노랑 / 정보 부족=회색)

### Phase F — 표본 확장 + 통합 검증

- [ ] HIRA → 서울 5개구 풀커버 (이슈 [#18](https://github.com/BORB-CHOI/clinic-focus/issues/18) 의 "병원 목록 소스" 부분)
  - 강남 4과목 88개 → 5개구(강남·서초·송파·성동·중구) 4과목 ~1000개 → 5개구 전체 진료과목 ~1만
- [ ] **풀크롤링 (1만 전체)** — 자체 사이트 + 외부 4소스(네이버 플레이스·블로그·카카오·구글). LLM·Vision 미사용
- [~] **룰 기반 분류 일괄 (트랙 A, 1만)** — 배치 스크립트 `be/scripts/run_classification.py` 준비 완료: DDB 순회 → `db.load_external_signals` 로 카카오/네이버/구글 entity 로드 → `classify_hospital(use_llm=False, **external)` → 분류 저장 + `build_signal_chunks(**external)` ingest, 마지막 1회 trigger. **실제 1만 실행은 외부 크롤 일괄 후** (외부 entity 적재돼 있으면 4 시그널 교차검증, 없으면 자체 사이트만 — graceful)
- [ ] **LLM 시연 분류 (트랙 B, 10개)** — `MAX_LLM_DEMO_HOSPITALS=10` 환경변수 강제. 풀커버 결과 중 발표용 10개 선정 (강남, 진료과목 다양, 사이트 풍부)
- [ ] **Vision 시연 (트랙 C, 같은 10개)** — `MAX_VISION_IMAGES=10` 환경변수 강제. Marketplace 구독 완료 전제. 같은 10개에 대해 트랙 B 결과와 비교 출력 (발표 자료용)
- [ ] **`generate_description` 시연 (10개)** — 트랙 B·C 결과 합쳐 자연어 통합 설명 생성. 9990개는 `ai_description=null` 그대로 (FE 차등 렌더링)
- [ ] `ingest_hospital` 일괄 — KB 에 1만개 본문 적재. 본문 합성 시 LLM 설명은 10개만 박히고, 나머지는 룰 기반 태그·외부 시그널 키워드 빈도로 본문 구성
- [ ] 자연어 검색 e2e — 다양한 쿼리(시술명·증상·지역+시술 조합) 10건 검증
- [ ] 의료법 표현 전수 검수 — `medical-language-reviewer` 서브에이전트 (특히 후기 키워드 노출 형태, AI 통합 설명, FE 카피)
- [ ] `shared/models.py` 변경분 BE·AI 동시 갱신 확인 (스키마 drift 0)
- [ ] FE→BE→AI→KB→DDB→9영역 응답 통합 E2E 시나리오 5건
- [ ] 비용 측정 — 1만개 처리 LLM·Vision·임베딩 실비용 → `overview.md` 10-1 추정치 보정

### Phase G — 인프라·운영 마무리

- [ ] systemd `clinicfocus.service` 검증 (PR #8 이미 있음)
- [ ] CloudFront + S3 정적 호스팅 — FE 빌드 → `aws s3 sync` → invalidation
- [ ] EC2 모니터링 — CloudWatch 기본 로그 (별도 인프라 X)
- [ ] `.env.example` 최종 정렬 — 누락 키 0
- [ ] README.md 최종 검수
- [ ] PR-단위 의료법·코드 리뷰 (`medical-language-reviewer`·`python-reviewer`·`typescript-reviewer`·`security-reviewer`)

---

## 5. 의존성 그래프

```
Phase A (기반 재설계)
  ├─ DDB 단일 테이블
  ├─ shared/models.py 확장
  ├─ 외부 API 키 발급
  └─ BE 차단 이슈 #23/#24
        │
        ▼
Phase B (외부 시그널 크롤러 4종)
  ├─ 자체 사이트 정제 (#13)
  ├─ 네이버 플레이스 + 블로그
  ├─ 카카오 (확장)
  └─ 구글 Places
        │
        ▼
Phase C (AI 본체화 + 4 시그널 통합)
  ├─ ai/scratch → ai/ 본체
  ├─ classify_hospital 재설계
  ├─ generate_description 4 시그널 종합
  ├─ Vision 활성화 (Marketplace 의존)
  ├─ extract / related / recompute / aggregate / 변경이력 자동 기록
        │
        ▼
Phase D (BE 4개 엔드포인트 본체)
  ├─ /api/search (자연어 + 지도)
  ├─ /api/hospitals/{id} (9영역)
  ├─ /api/hospitals/{id}/history
  └─ /api/feedback
        │
        ▼
Phase E (FE 9영역 + 시그널 시각화)
  ├─ 9개 컴포넌트 분리
  ├─ ai_description 차등 렌더링
  └─ 카카오맵 신뢰도 색 마커
        │
        ▼
Phase F (표본 확장 + 통합 검증)
  ├─ 88 → 1000 → 1만
  ├─ 의료법 전수 검수
  └─ 통합 E2E
        │
        ▼
Phase G (인프라·운영 마무리)
```

병렬 진행 가능:
- Phase A 내부 4 항목 병렬
- Phase B 의 4 크롤러 병렬 (소스별 독립)
- Phase C·D 의 인터페이스 합의 후 동시 진행
- Phase E 는 Phase D `/api/*` skeleton 만 있어도 진입 (Mock 가능)

---

## 6. AI 트랙 AWS 워크북 (개인 진행 기록)

| Step | 내용 | 상태 |
|---|---|---|
| 0 | VSCode Remote-SSH → EC2 | ✅ |
| 1 | 지원 계정 자격증명·Bedrock 모델 가용성 | ✅ |
| 2 | Titan v2 임베딩 hello-world | ✅ |
| 3 | KB Retrieve 왕복 + S3 ingest 권한 | ✅ |
| 4 | DataSource 파일·metadata 스키마 | ✅ |
| 5 | 개인 계정 Sonnet 4.6 Vision (Marketplace 구독 대기) | △ |
| 6 | DDB 7테이블 + 88개 적재 + 14개 분류·설명·KB ingest·자연어 검색 | ✅ PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) (V2 전환과 함께 옛 7-table·14개 폐기) |
| 7 | single-table 재설계 — 어댑터 재작성 + 옛 7-table 폐기 + 콘솔 수동 V2 생성 | ✅ 2026-05-27 |
| 8 | **외부 3소스 (네이버·카카오·구글) 적재** | ⏳ Phase B |
| 9 | **4 시그널 본문 합쳐 재 ingest** | ⏳ Phase C |

상세 진행 기록은 [`../setup/aws-onboarding.md`](../setup/aws-onboarding.md), `ai/scratch/run-log-2026-05-26.md` 참조.

---

## 7. 완료된 PR (최근순)

> 작업 내용별 누적 요약은 [`done-catalog.md`](done-catalog.md) 참조.

| PR | 제목 |
|---|---|
| [#36](https://github.com/BORB-CHOI/clinic-focus/pull/36) | 네이버 어댑터 2종 + HTML 정제 + alt_ids — V2 미개발 해소 |
| [#35](https://github.com/BORB-CHOI/clinic-focus/pull/35) | 외부 시그널 4종 통합 + Phase A/C/D 정합 (검색·피드백·분류 연동) |
| [#34](https://github.com/BORB-CHOI/clinic-focus/pull/34) | 카카오 어댑터 + AI 룰 분류·KB 시그널 청크 본체 + 정합 정리 |
| [#30](https://github.com/BORB-CHOI/clinic-focus/pull/30) | feat: 분류 스키마 22 후보군 확정 + 외부 API 키 변수 추가 |
| [#28](https://github.com/BORB-CHOI/clinic-focus/pull/28) | refactor(be): DDB V2 single-table 어댑터 재작성 |
| [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) | feat(ai): scratch/ 우회로 dev e2e 검증 — HIRA → 분류 → KB → 자연어 검색 |
| [#22](https://github.com/BORB-CHOI/clinic-focus/pull/22) | docs: DDB 선택 근거 + 7-table ERD 박기 |
| [#21](https://github.com/BORB-CHOI/clinic-focus/pull/21) | feat: URL 보강 크롤링 파이프라인 (Playwright + 쿼리 다변화) |
| [#20](https://github.com/BORB-CHOI/clinic-focus/pull/20) | docs(env): `AI_AWS_SESSION_TOKEN`·`CRAWL_DATA_DIR` 코멘트 명확화 |
| [#19](https://github.com/BORB-CHOI/clinic-focus/pull/19) | docs(ai): dev 계정 e2e Step 6 추가 + DDB 콘솔 수동 생성 절차 |
| [#17](https://github.com/BORB-CHOI/clinic-focus/pull/17) | docs(be): BE AWS 연결 작업 큐 + 의존성 매트릭스 |
| [#16](https://github.com/BORB-CHOI/clinic-focus/pull/16) | docs(ai): AWS 온보딩 Step 2·5 완료 + Vision Sonnet 4.6 전환 |
| [#15](https://github.com/BORB-CHOI/clinic-focus/pull/15) | docs(ai): 벡터 검색 KB 경유 전환 + AWS 온보딩 가이드 |
| [#14](https://github.com/BORB-CHOI/clinic-focus/pull/14) | feat(fe): FE 디자인 — 검색·상세·지도 화면 골격 |
| [#12](https://github.com/BORB-CHOI/clinic-focus/pull/12) | docs(ai): AI 트랙 전략 재편 + EC2/VSCode Remote-SSH 개발환경 확정 |
| #11 | feat(fe): 지도 검색 페이지 카카오맵 + 신뢰도 색 마커 |
| #9 | feat: Kiro 컨텍스트 공유 (`.kiro/steering/`) + docs/ 위치 통일 |
| #8 | feat(be): uvicorn EC2 진입점 (`be/main.py`) |
| #6 | feat(be): EC2 셋업 — `S3Adapter` 로컬 FS, `kakao_adapter`, systemd, FastAPI 응답 포맷 |

---

## 8. 운영 메모

### 계정 분리 (2026-05-25)
BE(`kmuproj-02`)·AI(`kmuproj-10`) 각자 자기 자원. 발표 정본은 BE 풀커버, AI 미니 표본은 개발용 — 단 single-table 재설계 후 이 분리도 재검토 필요 (양쪽이 같은 single-table 스키마면 데이터 이관 가능성).

### KB 공유 운영 규약 (강사 정책)
KB `kmuproj-team-03`(ID `GTBJ6HLFDK`) DataSource S3 `kmuproj-02-vector` 는 02·10·11팀 공유.

- Prefix 분리: `clinic-focus/prod/` · `clinic-focus/probe/`
- Delete 운영 코드 금지 (soft-delete: `metadata.status="closed"`)
- `team_id="clinic-focus"` 메타 필수 (Retrieve 필터 격리)

### Bedrock 모델 라우팅 (2026-05-26)
- 텍스트 LLM (Haiku 4.5) → 개인 계정 `ap-northeast-2` (지원 계정 inference profile 라우팅 deny)
- Vision (Sonnet 4.6) → 개인 계정 `ap-northeast-2` (Global cross-region inference profile)
- Titan Embed v2 → 지원 계정 `us-east-1` (KB 자동 호출)

### 의료법 §56 회피 — 후기 데이터 처리 (외부 시그널 시 절대 어기지 말 것)

| 항목 | 허용 | 금지 |
|---|---|---|
| 후기 본문 저장 | DDB 에 raw 저장 (내부 분석용) | — |
| 후기 본문 사용자 노출 | — | 개별 후기 본문 그대로 화면에 표시 ❌ |
| 후기 키워드 노출 | "친절·아토피·여드름·꼼꼼 키워드 빈도 N건" | — |
| AI 통합 설명에서 인용 | "후기 키워드 빈도 ~%" (출처 배지 `[후기]`) | "후기에서 호평" 같은 평가형 어조 ❌ |

### main 브랜치 직접 수정 금지
PreToolUse hook + pre-commit hook 양쪽 차단. 모든 작업은 feature 브랜치.
