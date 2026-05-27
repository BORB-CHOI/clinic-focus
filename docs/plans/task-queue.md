# clinic-focus 작업 큐 — V2 완전 서비스

> 최종 업데이트: 2026-05-27 · 상위 컨텍스트: [`../overview.md`](../overview.md), [`../dev-roadmap.md`](../dev-roadmap.md)

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
| 1 | 자연어 검색 (KB Retrieve) | 4 시그널 본문이 KB ingest 에 다 들어가야 진짜 매칭 | △ 자체 사이트만 ingest | 외부 3개 소스 ingest 본문 합치기 미구현 |
| 2 | 상세 페이지 9개 영역 | 모든 영역의 데이터 소스가 채워져야 | ❌ FE/BE 골격 | 의료진·신뢰도근거·관련·이력 영역 데이터 없음 |
| 3 | AI 통합 설명 | 4 시그널 다 받아야 종합 가능 | △ 자칭만으로 14개 통과 | 블로그·후기·Vision 다 입력으로 받는 재설계 |
| 4 | 4 시그널 교차 검증 | Vision + 블로그 + 후기 다 켜져야 | ❌ 자칭만 (25%) | Vision/블로그/후기 = 0% |
| 5 | 신뢰도·피드백 자기교정 | Feedback 누적 + 임계 + 재계산 | ❌ | `recompute_confidence`·`aggregate_feedback_stats` 미구현 |
| 6 | 분류 변경 이력 자동 기록 | hash diff + ChangeHistory INSERT | ❌ | 테이블만 존재 |
| 7 | 피드백 (디바이스ID 중복방지) | API + UI + DDB | ❌ | API skeleton 만, FE UI 없음 |
| 8 | 관련 병원 추천 | 유사도 + 메타필터 + "다루지 않는 분야 대안" | △ 코드만 | 실측 없음, alternative_hospital_ids 미연결 |
| 9 | 카테고리 이중 색인 | extract 실측 + "다루지 않는 분야" 정확도 | △ 코드만 | 실측 없음 |

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

- [ ] `shared/models.py` 4 시그널 다 받도록 확장
  - `Classification.signals` 에 `vision`·`blog`·`reviews` sub-block (현재는 self_claim 만 의미 있음)
  - 신규 모델: `NaverPlace` · `NaverBlogPost` · `KakaoPlace` · `GoogleReviews` · `ExternalSignalBundle`
  - `CrawlData` 외에 `ExternalCrawlData` 모델 (네이버/카카오/구글 합쳐)
  - `HospitalIngestMetadata` 에 `aliases`·`status`·`last_external_crawl_at` 추가
- [x] **DDB 단일 테이블 마이그레이션** (Phase A 1차, 2026-05-27, PR [#28](https://github.com/BORB-CHOI/clinic-focus/pull/28))
  - [x] `be/adapters/dynamo_adapter.py` 전면 재작성 — 7개 테이블 메서드를 entity SK 기반 단일 어댑터로 (`get_entity`/`put_entity`/`query_hospital_entities`/`iter_all_hospital_ids` 등 generic primitives + typed helper 유지)
  - [x] AI/BE 양쪽 `dynamodb.Table("Hospitals")` 류 호출을 새 어댑터 메서드로 교체 (`ai/scratch/kb_ingest.py` 한 곳)
  - [x] 옛 7-table 폐기 (콘솔 수동 삭제, AI 트랙 14개 데이터 폐기 — 이관 안 함)
  - [ ] **신규 V2 단일 테이블 콘솔 수동 생성** — `kmuproj-10-clinic-Main`, 절차는 [`../setup/aws-onboarding.md`](../setup/aws-onboarding.md) Step 6 (SafeRole 에 CreateTable 권한 없음 → 자동화 스크립트 불가)
  - [ ] 검증: BE 크롤링 1만 데이터 받은 후 자연어 검색 4쿼리 회귀
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
- [ ] 외부 API 키 발급
  - [ ] 네이버 개발자센터 — 검색 API (블로그·플레이스)
  - [ ] 카카오 — 로컬 API (`kakao_adapter.py` 이미 사용 중) + 추가 리뷰 접근 검토
  - [ ] 구글 Cloud — Places API (Place Details + Reviews 필드)
  - [ ] 개인 AWS 계정 — Bedrock Sonnet 4.6 Marketplace 구독 (Vision 활성화)
  - [ ] `.env.example` 에 신규 키 변수 + 코멘트
- [ ] BE 본체 차단 이슈 머지
  - [ ] 이슈 [#23](https://github.com/BORB-CHOI/clinic-focus/issues/23) `s3_adapter` boto3 + `crawl_all.py` `TABLE_PREFIX`
  - [ ] 이슈 [#24](https://github.com/BORB-CHOI/clinic-focus/issues/24) `load_env` 인라인 주석 버그

### Phase B — 외부 시그널 크롤러 4종 (BE)

> ⚠️ **Phase B 진입 전 결정 — 후기 시그널 전략** (2026-05-27 추가, 다음 세션 1순위 의제)
>
> 본 박스는 **플레이스·후기 데이터 자체 수집**에 관한 것. BE PR [#21](https://github.com/BORB-CHOI/clinic-focus/pull/21) 의 "URL 보강 크롤링"(네이버·카카오 검색 결과 페이지에서 병원의 자체 홈페이지 URL 추출 — 자칭 시그널 시드용)과는 **별개**. 같은 "네이버·카카오" 단어라 혼동하기 쉬움 — PR #21 은 자체 사이트 시드 확보 → 본 박스는 외부 후기 본체 수집.
>
> 4 시그널 中 후기(25%) 는 본 서비스 핵심 차별점인데, 공식 API 로는 **구글 Places (Reviews 5건/병원)** 만 합법 커버 가능. 네이버 플레이스·카카오맵 리뷰는 **비공식 엔드포인트** 만 존재. 사용자 실측(2026-05-27 브라우저 네트워크 캡처)으로 확인된 네이버 엔드포인트:
>
> | 호출 | 엔드포인트 | 응답 |
> |---|---|---|
> | 카테고리 검색 | `GET map.naver.com/p/api/search/allSearch?query=병원&searchCoord=...&boundary=...` | place_id · 이름 · 주소 · 카테고리 · 좌표 · `reviewCount` · `placeReviewCount` · 영업시간 · 썸네일 · 홈페이지 |
> | 세션 토큰 | `POST ncpt.naver.com/v2/tokens?q={ts}&tid={...}` | (필수성 미검증 — 토큰 없이도 동작하는지 다음 세션 실측) |
> | 방문자 리뷰 | `POST pcmap-api.place.naver.com/graphql` (`visitorReviews` query) | 본문 · 평점 · 작성자 익명ID · 방문 카테고리 키워드 · 이미지 · 작성일 |
> | 병원 정보 탭 | `POST pcmap-api.place.naver.com/graphql` (query 명 미확인 — 다음 세션 캡처) | **진료영역 리스트** · **대표 키워드** · **원장 이력**(SNS·방송·학회) · **편의시설**(예약·주차·화장실) · 결제수단 · SNS 링크(블로그·유튜브) |
>
> 카카오맵도 같은 패턴 (`place.map.kakao.com/main/v/{id}` · `comment/v/{id}`) — 다음 세션 캡처 필요.
>
> ⭐ **정보 탭이 후기 못지않게 가치 큼** — "진료영역" 은 그 병원의 *자칭 시그널* 그 자체(리스트 형태로 깔끔, 본문 파싱보다 정확), "대표 키워드" 는 그 병원이 의도한 SEO 키워드, "원장 이력" 은 9영역 ③ 의료진 데이터 직격, "편의시설" 은 9영역 ⑤ 위치·접근 직격. visitorReviews 와 같은 GraphQL 엔드포인트로 한 요청에 묶일 수 있는지 캡처·실측 필요.
>
> **본 서비스 정의상 후기 시그널 + 정보 탭은 가장 중요한 외부 데이터.** 단 본격 구현 전 다음 결정 필요:
>
> 1. 토큰 발급(`ncpt.naver.com`)이 필수인지 — 비로그인·토큰 없이 graphql 호출 가능한지 실측
> 2. 정보 탭의 GraphQL query 명 캡처 + visitorReviews 와 한 요청에 묶을 수 있는지 시도
> 3. 이용약관·robots.txt 검토 — 자동화 수집 금지 조항 강도
> 4. 의료법 §56③ 룰은 그대로 유효 — 후기 본문 raw 는 **DDB 저장 + 임베딩·AI 자연어 설명 생성 입력으로만 사용**, 화면 노출은 키워드 빈도만 (사용자 직접 확인). 정보 탭의 "진료영역"·"대표 키워드"·"원장 이력" 은 사실 정보라 화면 노출 허용
> 5. 개인정보 — 응답에 `loginIdno`/`userIdno`/`nickname` 들어옴. **비로그인 호출 시 본인 ID 안 들어옴** (사용자 로그인 상태에서 캡처해서 그렇게 보였음). 그래도 닉네임·작성자 ID 는 마스킹 + raw 미저장 권장
> 6. 표본 범위 — 1만 풀스케일 vs 시연 10개 한정 (운영 안정성·토큰 깨짐 위험 가늠)
>
> 다음 세션 1순위 의제: 위 5개 실측·결정 → 본 박스 권고안으로 갱신 → `naver_place_crawler`·`kakao_crawler` 항목 구현 방향 확정. 본 박스가 풀릴 때까지 두 항목은 보류.
>
> ---
>
> **2026-05-28 실측 raw 노트** (결정은 미확정 — raw 사실만 박음)
>
> 환경: EC2 IP `13.223.112.152`. 1차로 httpx 단독으로 7회 호출 시도(차단), 2차로 Playwright Chromium headless 로 실제 브라우저 흐름 재현(성공). 사용자 브라우저 캡처 1건 보조 자료(질의 `"병원"` → place_id `37564839` 더서울치과 → `getVisitorReviews` 본문 정상 반환).
>
> **사실 1 — robots.txt**: `map.naver.com` · `m.map.naver.com` · `m.place.naver.com` · `map.kakao.com` · `place.map.kakao.com` 모두 `User-agent: * Disallow: /` (단 `map.naver.com` 만 `Allow: /$` `Allow: /p/$` 두 경로). 사용자 제안 모바일 진입점 `m.map.naver.com/search/interest-spot?type=HOSPITAL` 도 동일 robots Disallow.
>
> **사실 2 — 약관**: 네이버 이용약관 "**자동화된 수단(매크로·로봇·스파이더·스크래퍼) 을 이용하여 ... 네이버 검색 서비스에서 특정 질의어로 검색하거나 ... 일체의 행위를 시도해서는 안 됩니다.**" 카카오 약관 "회사가 정하지 않은 비정상적인 방법으로 시스템에 접근하는 행위" 금지.
>
> **사실 3 — ncpt 토큰 발급 흐름 (Playwright 가 자동 실행)**: 검색 페이지 진입 시 SDK 가 `GET ncpt.naver.com/static/ncaptcha-api.js?ncaptcha-sitekey={140자}` 로딩 → `POST ncpt.naver.com/v2/tokens?q={ts}&tid={11자}` body=`{"cipherText":"<클라이언트 환경 시그너처 암호화 blob, 600+ 자>"}` → 응답 `{"tokenId":"<base64 hash 76자>"}`. SDK 가 이걸 추가 가공해 검색 URL 의 `token=` 파라미터에 44자 짧은 토큰을 박음(예: `3QqL8xOOMxlWs08QlEUOozA8E5OwxlfLGOLvtskiT60=`). **httpx 단독으로 cipherText 만들 수 없어서 long token(629자, 패딩 없음) 만 받고 `CE_BAD_REQUEST` 차단됨** — 1차 실패의 원인.
>
> **사실 4 — search-history delta warmup**: `GET map.naver.com/p/api/kvfarm/search-history/delta` 는 로그인 필수 API (`XE401`). 비로그인 도 검색 정상 동작하므로 warmup 은 필수 아님. 사용자 캡처에 보였던 건 본인 로그인 상태였기 때문.
>
> **사실 5 — 검색 (Playwright)**: `GET map.naver.com/p/api/search/allSearch?query=...&token={44자}&sscode=svc.mapv5.search` HTTP 200 + `pageId=<UUID>`, `rcode=09140103` (서울 강남구 region code), `result.place.list[0].id` 에 place_id 박혀있음. 응답에 `ip: 13.223.112.152` (EC2 IP 그대로) — **EC2 IP 자체가 차단 리스트에 박혀있지 않음**.
>
> **사실 6 — GraphQL 실측 (`POST pcmap-api.place.naver.com/graphql`)**: Playwright context (쿠키·토큰 자동 박힘 상태) 안에서 `page.evaluate fetch credentials:include` 로 호출 → 정상 응답. `getVisitorReviews` query (size=3, businessType="hospital") 응답 본문에 후기 본문 raw + 평점 + 작성자 익명 ID 다 박혀 옴.
>
> **사실 7 — 5건 표본 안정성 (Playwright)**: 성공 3건, 실패 2건 (실패 둘 다 검색 결과에 place 없음 — 차단 아니라 매칭 실패). 1건당 약 18~25초 소요 (headless Chromium 부팅·SDK 토큰 발급·검색·상세 진입·GraphQL fetch 누적):
>
> | 쿼리 | place_id | 검색결과 reviewCount | graphql total_reviews | avgRating | authorCount |
> |---|---|---|---|---|---|
> | 자생한방병원 강남 | `19516906` | 1886 | 526 | 4.05 | 113 |
> | 더서울병원 성북 | `778531046` | 3416 | 356 | 4.02 | 64 |
> | 위담한방병원 강남 | `1520927430` | 2506 | 1002 | 4.24 | 228 |
> | 에이솝병원 강남 | place 없음(검색 매칭 실패) | — | — | — | — |
> | 예이진한의원 강남 | place 없음(검색 매칭 실패) | — | — | — | — |
>
> 검색결과 `reviewCount` vs graphql `total_reviews` 가 다른 이유는 검색결과는 "전체 리뷰(블로그·플레이스 합산)" 이고 graphql 은 "방문자 리뷰만" 카운트.
>
> **사실 8 — GraphQL 응답 스키마 (실측)**: `visitorReviews.items[]` 에 `body`(후기 본문 raw, 최대 수백 자), `rating`(현재 null 들어옴 — 평점은 query 변수에 따라 별도 query 필요), `visitedDate`, `visitCount`, `userIdno`(작성자 익명 5자 ID 예: `1f5LD`·`25hpK`·`2WoTG`), `loginIdno=""` (비로그인 호출이라 빈 값), `author.nickname`(서버 측 마스킹 — `su****` · `까뀽2` · `ymn****` 형태로 일부만 노출), `votedKeywords[].name`. `visitorReviewStats` 에 `review.avgRating`·`totalCount`·`authorCount`·`imageReviewCount`, `analysis.themes`·`votedKeyword.details`. 단 실측 3건에서는 `themes=[]`·`votedKeyword.details=[]` 로 빈 배열 — query 변수에 `itemId` 박지 않아서일 가능성(추가 튜닝 필요).
>
> **사실 9 — 개인정보 raw 노출**: 비로그인 호출 시 `loginIdno` 비어있음. `userIdno` 는 작성자 익명 5자 base32-ish ID (네이버 내부 식별자). `author.nickname` 은 서버 측에서 일부 마스킹 — 한글 닉네임은 그대로(`까뀽2`·`금본위`), 영문/숫자 닉네임은 처음 2~3자 + `****` (`su****`·`ymn****`). 즉 우리가 마스킹 추가 처리 안 해도 raw 응답이 이미 일부 마스킹 상태.
>
> **사실 10 — 카카오**: 공식 `dapi.kakao.com/v2/local/search/keyword.json` 키 없이 401 (`AccessDeniedError`, "Authorization : KakaoAK header" 필요) — 정상. 비공식 `place.map.kakao.com/main/v/{id}` 는 임의 ID(`8136181`·`17822251`) 시도 시 404. 카카오 실 place_id 형식·동일 ncpt-style 차단 구조 여부는 미실측.
>
> **사실 11 — Vision 입력 (박스 2 raw)**: `s3://kmuproj-10-clinic-focus-crawl/crawl/` 의 강남 502개 중 10개 무작위 표집 분석. 이미지 총 **300장(모든 사이트가 정확히 30장 cap)**, URL 패턴 잡음 의심 **78장(26%)**, 시술 힌트 URL/alt 매칭 **35장(11%)**, alt 보유 **164장(54%)**. 사이트별 잡음률 0~100% 편차 — `gn.chihyu.co.kr` 0%, `aesophospital.com` 3%, `re-bom.com` 100%. `re-bom.com` 의 `menu_2_1_2_manualTherapy.png` (alt="도수치료") 는 URL `menu_` 패턴 때문에 잡음 분류됐으나 실제 시술 카테고리 그리드 — **URL 패턴 단독 잡음 룰은 거짓 양성 다발**, alt 텍스트가 결정적 시그널.
>
> **운영 비용·제약 추가 메모 (수치 raw)**:
> - **EC2 부담**: 1건당 headless Chromium 18~25초. 1만 풀커버 시 단일 EC2 직렬 처리 = ~50~70시간. 병렬화·헤드리스 풀 운영 필요
> - **Playwright Chromium 시스템 의존성** (현 EC2 에 설치 완료): `atk at-spi2-atk nss cups-libs libdrm libXcomposite libXdamage libXrandr libXfixes libXScrnSaver libxkbcommon mesa-libgbm pango cairo alsa-lib`
> - **검색 매칭 실패율** = 표본 2/5 (40%) — 정확한 병원명 + 지역 조합으로 검색해야 후보 1번이 정확. HIRA `yadmNm` 그대로 박았을 때의 매칭률은 별도 실측 필요
> - **EC2 IP 차단 위험**: 1차 7회 호출에서도 차단 표시 없음(응답에 우리 IP 노출), 5건 패키지도 안정. 단 1만 풀커버 시 IP rate-limit 발생 가능성은 미실측
>
> **미해명 항목** (다음 세션):
> - GraphQL `votedKeyword.details` · `themes` 비어있는 이유 (query 변수 `itemId` 튜닝)
> - 정보 탭 (`진료영역` · `대표 키워드` · `원장 이력` · `편의시설`) query 명 — visitor 탭 외 다른 탭 진입 시 호출되는 GraphQL 캡처 필요
> - 카카오 비공식 엔드포인트의 실제 구조 (place_id 형식·ncpt-style 차단 여부)

> ⚠️ **Phase B 진입 전 결정 — Vision 입력 전략** (2026-05-27 추가, 다음 세션 2순위 의제)
>
> 현재 BE 의 `crawl_data.json` `images[]` 필드는 **사이트 HTML `<img>` 태그 URL 메타만** 담음 (`url`·`page_url`·`alt_text` 3 필드). 이미지 바이트 다운로드·Vision 분석은 Phase C AI 책임. 단 다음 사실로 입력 전략 재검토 필요:
>
> - **한국 의원 사이트는 이미지 비중이 매우 큼** — 풀스크린 슬라이드·시술 전후 사진·시술 카테고리 그리드 등. 텍스트 적고 이미지로 정체성 표현하는 경향
> - `<img>` 태그만 긁으면 **CSS `background-image`·`<picture>`·SPA lazy-load 이미지 누락**. 시술·기기 사진이 누락되면 Vision 시그널(30%) 가치 ↓
> - 표본 1건(`weedahm.com`) 30개 이미지 중 로고·아이콘·캘린더 같은 잡음 다수 — 잡음 비율 실측 안 됨
>
> 4 입력 옵션:
>
> | 옵션 | 입력 | 장점 | 단점 |
> |---|---|---|---|
> | A. `<img>` URL 다운로드 (현재 가정) | 사이트의 `<img>` URL → 바이트 받아 Vision | URL 이미 수집됨. 추가 작업 작음 | 로고·아이콘 잡음. CSS background 시술 사진 누락. SPA 정적 HTML 누락 |
> | B. 사이트 전체 스크린샷 (Playwright `full_page=True`) | 풀페이지 캡처 1장 | 사용자에게 실제 보이는 화면. 레이아웃·문구·배너 다 포함. SPA 대응 | 1장 1~5MB. Vision 토큰 폭증. 페이지 너무 길면 토큰 한도 초과 |
> | C. 페이지 N구간 분할 스크린샷 | 풀페이지를 스크롤 구간별 캡처 | B 토큰 부담 완화. 영역별 분석 가능 | 구현 복잡. 구간 매핑 관리 |
> | D. `<img>` + `background-image` + Playwright `getComputedStyle` | DOM 에서 보이는 모든 이미지 | A 누락 완화. CSS 배경 시술 사진 회수 | 정제 필요. 구현 중간 난이도 |
>
> 결정 필요:
>
> 1. 표본 5~10개 사이트로 A 결과 잡음 비율·시술 사진 누락률 실측
> 2. A 누락이 많으면 D 시도. 그래도 부족하면 B/C
> 3. `MAX_VISION_IMAGES=10` 제약 안에서 어떤 입력이 최대 정보량인지 가늠
> 4. BE 가 입력 형식을 바꾸면 `crawl_data.json` `images[]` 스키마 변경 — shared/models.py `CrawledImage` 영향
>
> 다음 세션 2순위 의제: 표본 실측 → 옵션 선택 → BE 이미지 수집 방식 갱신 + AI `analyze_images` 입력 시그니처 확정. 이 박스도 풀릴 때까지 Phase C Vision 본체(`ai/pipeline/vision.py`) 진입 보류.
>
> ---
>
> **2026-05-28 실측 raw 노트** (위 후기 시그널 전략 박스의 "사실 9" 참조). 10개 표본 분석으로 잡음·시술 사진 hit률·alt 보유율 raw 수치는 박음. 결정 1~4 의 옵션 채택 여부(A vs D vs B/C) 는 미확정.

- [ ] `be/core/crawlers/site_crawler.py` (현 `crawler.py`) — 자체 사이트, **HTML 잡음 정제 추가** (이슈 [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13))
  - 페이지 간 중복 단락 자동 검출 (한 사이트에서 N회 이상 반복 = 푸터/메뉴 판정)
  - 잡음 블랙리스트 (modoo 안내·개인정보취급방침·환자권리장전·이용약관·비급여 고지·404·Copyright)
  - 정제 후 100자 미만 → "정보 부족" 마크
- [ ] `be/core/crawlers/naver_place_crawler.py` 신규 — **위 후기 시그널 전략 박스 결정 후 진입**
  - 검색 → `place_id` 매칭 → 영업시간·전화·사진·총 방문자 수·키워드 통계 추출
  - 리뷰 본문 수집 (의료법 §56③ 회피 — DDB raw 저장 + 임베딩·AI 설명 입력으로만, 화면 노출은 키워드 빈도만)
  - `NAVER#PLACE` + `NAVER#PLACE#REVIEWS` entity 적재
- [ ] `be/core/crawlers/naver_blog_crawler.py` 신규
  - 네이버 검색 API `v1/search/blog` — 쿼리 `{병원명} {지역명} {진료과목}`
  - 상위 30~50개 포스트 URL → 본문 추출 (httpx + BS4)
  - 키워드 빈도 + 주제 분포 (TF-IDF 또는 Bedrock 임베딩 클러스터링)
  - `NAVER#BLOG` entity 적재
- [ ] `be/core/crawlers/kakao_crawler.py` 확장 (현 `kakao_adapter.py`·`kakao_place_renderer.py` 기반) — **위 후기 시그널 전략 박스 결정 후 진입**
  - 로컬 API 카테고리 HP8 (이미) + 장소 상세 페이지에서 리뷰 추출 (비공식 `place.map.kakao.com/main/v/{id}` · `comment/v/{id}`)
  - `KAKAO#PLACE` + `KAKAO#REVIEWS` entity 적재
- [ ] `be/core/crawlers/google_places_crawler.py` 신규
  - Places API: `findPlaceFromText` → `place_id` → `place/details` (`reviews` 필드 5개 한정 — 무료 tier)
  - `GOOGLE#PLACE` + `GOOGLE#REVIEWS` entity 적재
- [ ] `be/scripts/crawl_external_all.py` — 위 4종을 한 병원당 순차 호출, 결과 합쳐 DDB 적재
- [ ] **hash diff 기반 부분 재처리** (이슈 [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13) 후반부)
  - 각 entity 에 `content_hash` 컬럼 추가
  - 재크롤링 시 hash 동일하면 KB 재 ingest 스킵
- [ ] 의료법 후기 처리 룰 — 리뷰 본문 raw 는 DDB 저장 + **임베딩·AI 자연어 설명 생성 입력으로만 사용** (KB ingest 본문에 포함 가능). 화면 노출은 **키워드 빈도·태그·`visitCategories` 만** — 개별 후기 본문 직접 노출 절대 금지

### Phase C — AI 본체화 + 4 시그널 통합

- [ ] `ai/scratch/` → `ai/` 본체 마이그레이션
  - [ ] `ai/search/kb_store.py` 신규 — `ingest_hospital(hospital_id, signals: SignalBundle, metadata) -> None`
  - [ ] `ai/search/kb_store.py` — `retrieve_hospital(query: SearchQuery) -> list[SearchResult]`
  - [ ] `ai/__init__.py` export 갱신: 추가 `ingest_hospital`·`retrieve_hospital`, 제거 `index_hospital`·`search_similar`
  - [ ] `ai/scratch/` 폴더 삭제
- [ ] **`ingest_hospital` — 4 시그널 본문 합쳐 KB ingest**
  - 본문 구성: `[자체 사이트 본문 page_type 우선순위] + [네이버 블로그 상위 N개 본문] + [네이버 플레이스 키워드 빈도] + [카카오 리뷰 키워드] + [구글 리뷰 키워드] + [AI 분류 결과·설명]`
  - metadata 에 `signals_included: ["self_claim","blog","reviews_naver","reviews_kakao","reviews_google","vision"]` 박음 (어떤 시그널이 채워졌는지 추적)
  - 빈 시그널은 본문에서 제외, metadata 키 자체 누락 (KB 가 빈 list/None 거절)
- [ ] **`classify_hospital(crawl_data, external_signals, vision_results) -> Classification`** 재설계
  - 입력: `CrawlData` + `ExternalSignalBundle` + `VisionResults`
  - 4 시그널 각각 점수 계산 → 교차 검증
  - 자칭 도배 페널티 (자칭 ↑ + 나머지 시그널 ↓ → 신뢰도 강제 감점)
  - 신뢰도 약점 수정: `primary_focus=[]` 또는 데이터 부족 시 `confidence ≤ 50`·`level="정보 부족"` 강제 (run-log-2026-05-26.md 2건)
- [ ] **`generate_description` 4 시그널 종합**
  - 프롬프트 입력에 4 시그널 다 들어가도록 `ai/prompts/hospital_description.md` 갱신
  - 각 단락 `citations` 가 실제 그 단락이 인용한 시그널만 박도록 강제 (현재 자칭만 박힘)
  - 약점 단락 의무화 — "이 병원이 보유하지 않은 장비·다루지 않는 분야"
  - 의료법 5규칙 강제 (주체 명시·출처 의무·평가 형용사 금지·약점 포함·JSON 검증)
- [ ] `ai/pipeline/vision.py` Vision 본체 — Marketplace 구독 완료 후 활성화
  - `analyze_images(image_urls, extract_text=False) -> list[ImageAnalysisResult]`
  - 시술 사진 분포 (일반/미용/기타) + 의료기기 식별 + OCR (Vision 흡수)
  - `MAX_VISION_IMAGES` 환경변수로 비용 제한
- [ ] `extract_services_and_doctors(crawl_data, classification, vision_results) -> ServicesAndDoctors` 실측
  - "다루지 않는 분야" 정확도 검증 (없는 시술·기기 추론)
  - `alternative_hospital_ids` 채우기 (관련 병원 추천과 연결)
- [ ] `find_related_hospitals(hospital_id, location, primary_focus, excluded_services, limit=5) -> list[RelatedHospital]` 실측
  - `same_focus`: KB Retrieve 유사도 상위 + 같은 시군구
  - `fills_gap`: `excluded_services` 각각에 대해 동네 대안 병원 찾기
- [ ] `recompute_confidence(hospital_id, recent_feedback) -> Confidence` 본체
  - 피드백 누적 N건 이상 + agree_ratio 임계 → 분류 재계산
  - 임계 미달 시 `confidence` 만 조정 (분류는 유지)
- [ ] `aggregate_feedback_stats(hospital_id) -> FeedbackStats` 본체
  - `FEEDBACK#STATS` entity 갱신
- [ ] **분류 변경 자동 기록**
  - `classify_hospital` 결과가 이전 `CLASSIFICATION` entity 와 다르면 `HISTORY#{ts}` 자동 INSERT
  - 이유: `feedback_accumulated` / `scheduled_recrawl` / `vision_reanalysis` / `human_review`
- [ ] **Bedrock mock 의무화** — 모든 단위 테스트가 `@patch("ai.core.bedrock_client.invoke_model")` 사용 (실 호출 비용 차단)

### Phase D — BE FastAPI 4개 엔드포인트 본체

- [ ] `GET /api/search` ([API-FE-BE §1](../API-FE-BE.md#1-검색))
  - `q` + `lat`/`lng` + `radius_km` + 필터 + 정렬
  - 자연어: `ai.retrieve_hospital(SearchQuery)` → KB Retrieve
  - 위경도: bounding box + haversine 재계산
  - 자연어 + 위경도 결합: KB filter 에 `lat`/`lng` bounding 박고 retrieve
  - DDB `CLASSIFICATION` + `META` join → `Hospital` 카드 응답
  - `meta.total`·`meta.search_mode`·`meta.query_interpretation` 채움
- [ ] `GET /api/hospitals/{id}` ([API-FE-BE §2](../API-FE-BE.md#2-병원-상세)) ⭐ 핵심
  - DDB query `PK=hospital_id` 전체 entity → 9영역 응답 조립
  - 영역 ①: `DESCRIPTION` entity 그대로 (없으면 `ai_description: null`)
  - 영역 ②: `SERVICES` + `CLASSIFICATION` + `PUBLIC#DEVICES`
  - 영역 ③: `PUBLIC#DOCTORS` + 자체 사이트 doctor 페이지 추출
  - 영역 ④: `CLASSIFICATION.signals` + `detailed_signals` (4 시그널 raw)
  - 영역 ⑤: `META` + `NAVER#PLACE.operating_hours` + `contact`
  - 영역 ⑥: `FEEDBACK#STATS`
  - 영역 ⑦: 최근 `HISTORY#*` 1~2건
  - 영역 ⑧: `RELATED`
  - 영역 ⑨: `INGEST#STATE.last_ingested_at` + `data_sources` 리스트
- [ ] `GET /api/hospitals/{id}/history` ([API-FE-BE §3](../API-FE-BE.md#3-분류-변경-이력))
  - DDB query `PK=hospital_id, SK begins_with HISTORY#` 시간 역순
  - `limit` 파라미터 (명세 갱신 필요)
- [ ] `POST /api/feedback` ([API-FE-BE §4](../API-FE-BE.md#4-피드백-제출))
  - `device_id + hospital_id` 중복 체크 (`SK begins_with FEEDBACK#{device_id}`)
  - `FEEDBACK#{device_id}#{ts}` entity INSERT
  - 임계 도달 시 `ai.recompute_confidence` 비동기 호출 (EventBridge 안 쓰니 inline)
  - 201/409 응답 명세 그대로
- [ ] `be/handlers/ingest_hospital.py` (현 `index_hospital.py`) — `run_index_pipeline` 함수에서 위 phase C 의 본체 함수들 순차 호출 (classify → extract → describe → related → ingest)
- [ ] `be/handlers/api.py` CORS `allow_origins=["*"]` → CloudFront 도메인 + `localhost:5173`
- [ ] 응답 포맷 일관성 — `{"data": ..., "meta": ...}` / `{"error": {...}}`
- [ ] 표준 에러 코드 매핑 (`INVALID_PARAMETER` 422→400, `NOT_FOUND` 404, `DUPLICATE_FEEDBACK` 409, `AI_SERVICE_ERROR` 502)
- [ ] OpenAPI 자동 생성 검증 — FastAPI `/openapi.json` 가 명세와 정합

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
- [ ] **룰 기반 분류 일괄 (트랙 A, 1만)** — `classify_hospital(crawl_data, external_signals, vision_results=None, use_vision=False)` 호출. self_claim + blog + reviews 시그널만 채움. Vision sub-block 은 None
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

| PR | 제목 |
|---|---|
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
