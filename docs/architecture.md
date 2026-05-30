# clinic-focus 데이터·분류 아키텍처

> 데이터가 **어디 저장되고**, 분류 결과가 **어떤 구조이며**, 4시그널이 **어떻게 하나의 신뢰도로
> 합쳐지되 개별 보존되는지**를 한곳에 모은 참조 문서.
> 작업 큐는 [`plans/task-queue.md`](plans/task-queue.md), 신호 실험 로그는 [`CATALOG.md`](CATALOG.md),
> 트랙별 상세는 각 `*/CLAUDE.md`. 이 문서는 "구조"만 다룬다.

---

## 0. 한눈에

```
                          ┌─ raw 수집 ───────────────┐    ┌─ 가공 산출 ───────────────────────┐
  HIRA · 카카오/네이버     │ 자체사이트 본문 → S3      │    │ 룰 분류(전수) → CLASSIFICATION    │
  · 심평원 · (자체사이트)  │ 플레이스/블로그/후기 → DDB │  → │ LLM·Vision(10개) → DESC/SERVICES │
                          └──────────────────────────┘    │ 임베딩 청크 → KB 벡터             │
                                                          └──────────────────────────────────┘
   저장 3층:  본문 = S3   /   벡터 = KB(Bedrock)   /   메타·가공·수집메타 = DynamoDB
```

핵심 3가지 (자주 헷갈리는 지점):
1. **분류는 한 단어가 아니다** — `standard_specialty`(22개 중 1) + `primary_focus`(자유 태그 **리스트**) 2축.
2. **4시그널은 하나의 숫자로 뭉개지지 않는다** — `confidence.signals` 에 4개 기여도가 **개별 보존**(`int|None`).
3. **본문·벡터는 DDB가 아니다** — 자체사이트 본문은 **S3**, KB 벡터/청크는 **Bedrock KB 내부**(DDB엔 포인터만).

---

## 1. 저장 구조 3층

### 1-1. DynamoDB `kmuproj-10-clinic-Main` (AI) — 메타·수집메타·가공 산출
`PK = hospital_id (S)` · `SK = entity (S)`. 한 병원의 모든 entity를 1회 Query.

| 구분 | entity | 비고 |
|---|---|---|
| **기준** | `META` | HIRA 종별·주소·좌표 + 카카오 보강 |
| **raw · 자체사이트** | `SITE#PAGES` · `SITE#IMAGES` | ⚠️ **본문은 DDB 아님 → S3** (아래 1-2) |
| **raw · 외부수집** | `NAVER#PLACE`·`NAVER#PLACE#REVIEWS`·`NAVER#BLOG` · `KAKAO#PLACE`·`KAKAO#REVIEWS`·`KAKAO#BLOG` · `GOOGLE#PLACE`·`GOOGLE#REVIEWS` · `PUBLIC#DEVICES`·`PUBLIC#DOCTORS` | 플랫폼 수집 원본 |
| **가공 · 룰 (1만 전수)** | `CLASSIFICATION` | 4시그널 교차검증 → 과목·주력·신뢰도. LLM 0회 |
| **가공 · LLM·Vision (시연 10개)** | `VISION#RESULTS` · `DESCRIPTION` · `SERVICES` · `RELATED` | Vision·`generate_description`·시술/의사·연관병원 |
| **가공 · KB** | `INGEST#STATE` | `content_hash`·`last_ingested_at`·KB object key (재적재 스킵용) |
| **사용자·시스템** | `FEEDBACK#{device}#{ts}` · `FEEDBACK#STATS` · `HISTORY#{iso}` | 1-tap 피드백·집계·분류 변경 이력 |

**GSI**: `sigungu-specialty-index`(PK=`sigungu#standard_specialty`, SK=`confidence_score`↓ — 카테고리 탐색
BE 직접) · `geo-index`(PK=`geohash_prefix`, SK=`lat#lng` — 지도 근처).

### 1-2. S3 `kmuproj-10-clinic-focus-crawl` — 자체사이트 본문(raw)
```
crawl/{hospital_id}/
  ├── crawl_data.json   ← CrawlData 전체 (AI 가 읽는 인터페이스). 분류·청크의 자칭 입력원
  ├── raw/{page}.html   ← 원본 HTML
  └── images/{file}     ← 이미지 바이너리
```
`be/adapters/s3_adapter.py`: `BUCKET=env(S3_CRAWL_BUCKET)`, key=`crawl/{id}/crawl_data.json`,
`save_crawl_data`/`load_crawl_data`. **본문이 1MB+ 라 DDB(400KB 한도) 아닌 S3에 둔다.**

### 1-3. Bedrock KB DataSource S3 `kmuproj-02-vector` + KB 내부 인덱스 — 벡터(검색)
```
clinic-focus/prod/{hospital_id}/
  ├── self_claim.txt(.metadata.json)   ← signal_type 별 청크 (아래 §4)
  ├── blog.txt(.metadata.json)
  ├── reviews.txt(.metadata.json)
  └── vision.txt(.metadata.json)
        │
        └─→ Bedrock KB: 청킹 → Titan Embed v2 임베딩 → 벡터 인덱스 (KB 내부)
```
⚠️ **청크·벡터는 DDB에 없다.** DDB `INGEST#STATE` 엔 hash·KB key 포인터만. 검색은 KB Retrieve API.

---

## 2. 분류 결과 구조 (`Classification`) — 한 단어가 아니다

`shared/models.py`. `model_config = extra="forbid"`.

```python
class Classification(BaseModel):
    hospital_id: str
    standard_specialty: str          # 축①: 22개 표준 진료과목 중 1 (행정·법적, GSI·필터용)
    primary_focus: list[str]         # 축②: 실제 주력 태그 리스트 (자유 문자열, 자율 추출)
    confidence: Confidence           # 축③: 신뢰도 (4시그널 개별 보존)
    detailed_signals: DetailedSignals
    classified_at: datetime
    classifier_version: str
```

- **축① `standard_specialty`** — `str`(Literal 미강제, 22개는 약속 + 단위테스트·검수로 무결성).
  카테고리 검색·GSI `sigungu#standard_specialty`·FE 필터가 의지. → 22 후보군은 [`ai/CLAUDE.md` "분류 스키마"](../ai/CLAUDE.md).
- **축② `primary_focus`** — `list[str]`. 사전 한정 없음. 예: `['여드름','흉터·모공','기미·색소','보톡스·필러']`.
  4시그널이 TF-IDF·명사구로 자율 추출. 상세페이지 태그 카드에 그대로 렌더.

### 2-1. `Confidence` — 4시그널 개별 보존
```python
class Confidence(BaseModel):
    score: int                                       # 0~100 종합 점수
    level: Literal["확실", "추정", "정보 부족"]
    signals: SignalContributions                     # ← 4시그널 각각의 기여도

class SignalContributions(BaseModel):                # 핵심: int|None 로 3상태 구분
    self_claim: int | None = None
    vision:     int | None = None
    blog:       int | None = None
    reviews:    int | None = None
```
| 값 | 의미 | 화면 |
|---|---|---|
| `int` 양수 | 수집됨 + top_focus 지지 (기여 %) | 기여도 막대 |
| `0` | **수집됐으나 주력과 엇갈림** | 0% (엇갈림) |
| `None` | **미수집(결손)** | 회색 "수집 안 됨" 배지 |

→ score 하나로 보여줄 수도 있지만, **4시그널 기여도가 그대로 남아** FE Confidence 영역이 분해 차트로 렌더.
`detailed_signals`(SelfClaim/Vision/Blog/Review 각 모델: 키워드·주제·기기·도배스코어 등)는 더 깊은 원천.

---

## 3. 4시그널 교차검증 (`ai/pipeline/classify.py`)

### 3-1. 가중치 (합 1.0, present끼리 재분배)
```python
_WEIGHTS = {"self_claim": 0.25, "vision": 0.30, "blog": 0.20, "reviews": 0.25}
```
Vision이 위조 난이도(시술·기기 사진) 때문에 최고. **결손 시그널은 점수 풀에서 빠지고 present끼리 재분배** —
3종만 있으면 그 3종 가중치를 1.0으로 정규화(빠진 1종에 반값·0 주지 않음).

### 3-2. 산출 흐름 (`_cross_validate_signals` → `_compute_confidence`)
1. 각 시그널의 `primary_focus`/`primary_topics`/이미지 카테고리를 focus 투표로 → 정규화(시그널 내 비율).
2. focus별 가중합 → 상위 = `primary_focus`, 1위 = `top_focus`.
3. **시그널별 일치도** `alignment(s) = norm_s[top_focus]` (그 시그널이 top_focus를 지지하는 정도 0~1).
4. **기여도** `contribution(s) = 재분배가중치(s) × alignment(s) × 100` (present만, 결손=None).
5. `score = Σ present contribution`.

### 3-3. 등급 — **근거 종류 수가 천장** (PR #41 결손 처리)
```
LOW = 70, HIGH = 95, CONFIDENCE_LEVEL1_CAP = 70, MIN_CERTAIN_SIGNALS = 2
```
- `score < 70` → **정보 부족**
- `70 ≤ score < 95` → **추정**
- `score ≥ 95` **이고** present(일치) 시그널 종류 ≥ 2 → **확실**
- present 시그널이 **1종뿐이면 score가 높아도 70(CAP)에서 막혀** "확실" 불가 — 단일 신호 과신 방지.
  → Vision·네이버가 미수집이면 대부분 2종 이하라 "확실"이 적게 나오는 게 정상(현 강남 실측: 확실 10).

### 3-4. 자칭 도배 페널티 (`_apply_spamming_penalty`)
자칭 `spam_score` 가 높고(키워드 도배) **자칭 primary_focus 와 외부(블로그·후기) 교집합이 0**이면 →
독립 시그널이 자칭을 반박하는 것으로 보고 신뢰도를 깎는다. "자기 사이트에만 도배"를 외부가 못 받쳐줄 때.

---

## 4. 임베딩 청크 (`ai/search/kb_store.py`)

`build_signal_chunks(...) -> dict[signal_type, str]` — 비어있지 않은 시그널만. 각 청크는 **임베딩 전용
자연어 텍스트**(화면 미표시, 의료법 §56③). signal_type = `self_claim` | `blog` | `reviews` | `vision`.

| 청크 | 합치는 소스 | 본문 헤더 |
|---|---|---|
| `self_claim` | 자체사이트(main/about/service) + 카카오 자칭(tags·소개·HIRA) | `[자체 사이트 자칭 정보]` / `[카카오 자칭 정보]` |
| `blog` | 자체 blog 페이지 + **카카오 place앵커 blog seeds** + (네이버 posts) | `[자체 사이트 블로그]` / `[카카오 블로그 …]` |
| `reviews` | 카카오·네이버·구글 후기 키워드 빈도 + 본문(임베딩 전용) | `… 강점 키워드 (총 N건/평균 X점)` |
| `vision` | `analyze_images` 결과 (기기·카테고리 분포). **시연 10개만** | `[Vision 분석 — 이 병원이 공개한 사진 …]` |

**사이드카 메타** `build_ingest_metadata(meta, classification)` → `{"metadataAttributes": {...}}`:
`team_id`(필수, KB 격리) · `hospital_id` · `name` · `standard_specialty` · `primary_focus` · `sido` ·
`sigungu` · `confidence_score` · `lat` · `lng`. → KB Retrieve 메타필터(시군구·과목·신뢰도) 근거.

`ingest_hospital(...)`: 청크 `{prefix}{id}/{signal}.txt` + `.metadata.json` 을 DataSource S3에 PUT,
배치는 `trigger_ingestion=False` 로 적재 후 마지막에 `StartIngestionJob` 1회.

### 4-1. 사전(.md) 기반 임베딩 동의어 보강 — 한국어 의학 어휘 갭 메우기

**문제**: Titan Embed v2 는 한국어 의학 동의어 갭이 크다(예 "사마귀" ↔ "심상성 우췌" cos ≈ 0.25).
병원 본문이 학명("심상성 우췌")으로만 적혀 있으면 사용자가 "사마귀"로 검색해도 임베딩이 안 잡힌다.
쿼리 확장만으로는 쿼리에 트리거 단어가 정확히 있어야 해서 취약하다.

**해결 — 사전 파일 `ai/data/medical_dictionary.md`** (142KB, 진료과별 표):
```
## 진료과: 피부과
| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
| 여드름 | acne, 심상성 좌창, 좌창, 면포, comedone, 아크네 | 여드름·흉터 |
```
- `ai/search/dictionaries.py` 가 이 .md 를 파싱 → `build_synonym_clusters()` 로 동의어 클러스터 생성.
- **두 곳에서 소비** (양방향 확장):
  - **문서 측**(`kb_store._enrich_with_synonyms`) — 청크에 클러스터 멤버가 하나라도 있으면 나머지를
    `[관련 의학 용어] …` 줄로 덧붙임(최대 60개). 본문이 어느 표현을 쓰든 임베딩이 일반어·학명·영문을 다 담음.
  - **쿼리 측**(`process_query`) — 검색어를 동의어·진료과로 확장.
- **장치**: 길이 2 미만 멤버(점·목·침)는 트리거로 안 씀(부분문자열 오매칭 차단). 임베딩 전용(화면 미표시)이라 §56 무관.
- **의료법**: .md 자체가 효능·광고어(최고·전문·완치) 금지 + medical-language-reviewer 검수 통과. focus 라벨의
  효능·심미 암시는 중립화(재생→치료, 심미→미용). 표준 시술명은 사실 용어라 recall 위해 유지(미노출).

→ **"왜 자체사이트 1만 풀커버인데 검색이 되나"의 핵심**: 비싼 LLM 재작성 없이, 사전 .md 한 장으로
문서·쿼리 양쪽 어휘를 맞춰 한국어 의학 검색 recall 을 끌어올린다.

---

## 5. 검색 시점 — LLM 0회 (Semantic Search)

자연어 쿼리: AI `retrieve_hospital` → **KB Retrieve 1회**(내부에서 Titan 임베딩+벡터검색) + DDB 신뢰도 조회.
카테고리 탐색(`sigungu & specialty` 전체목록): BE가 **DDB GSI 직접**(KB 미경유). 검색에 Sonnet/Haiku 호출 없음.

> 출처 명시·평가어 금지 등 의료법 원칙은 [`../CLAUDE.md`](../CLAUDE.md) "의료법 회색지대" + [`ai/CLAUDE.md`](../ai/CLAUDE.md)
> `generate_description` 원칙. 후기 본문 raw 는 임베딩 입력만, 화면은 키워드 빈도만.

---

## 6. 현재 미수집 시그널·데이터 한계 (2026-05-30, 솔직본)

스키마엔 자리가 있으나 **아직 안 채워진** 것들. PoC 범위·외부 제약 때문이며, 영향과 함께 명시한다.

| 미수집 | 현황 | 원인 | 영향 |
|---|---|---|---|
| **의료기기** (`registered_devices`) | `public_data` **0/2133 빈값**, `PUBLIC#DEVICES` 엔티티 0 | 심평원 공공 API 의 기기 신고 데이터 미연동 | 상세페이지 **장비 영역 비고**, **"병원이 공식 신고한 의료기기" 적법표현 근거 없음** |
| **의사·전문의** (`specialists`/doctors) | `public_data.specialists` **빈값**, `PUBLIC#DOCTORS` 0 | HIRA `getHospBasisList` 응답에 진료과목·전문의(`dgsbjtCdNm`) 없음 — 미연동 | 상세페이지 **DoctorsSection 빈값**, `extract_services_and_doctors` 의 의사 파트 비게 됨 |
| **Vision** (이미지 분석 30%) | `VISION#RESULTS` 0, `SignalContributions.vision = None` | 개인계정 Sonnet Marketplace 구독 대기(사용자 트랙) | 4시그널 중 1축 결손 → **근거 종류 수 천장**에 자주 걸려 "확실" 적음 (§3-3). 시연 10개 활성화 시 그 10개만 채움 |
| **네이버 플레이스 후기** | `NAVER#PLACE#REVIEWS` 0 | 회색지대 Playwright(18~25초/건) → 로컬 PC 크롤로 분리(보류) | 후기 시그널이 카카오 단독. 로컬 raw 도착 시 합류 |
| **가공 산출(시연 10개)** | `DESCRIPTION`·`SERVICES`·`RELATED` 0 | LLM 데모 미실행 | 9990개는 `ai_description=null` (FE 태그카드 차등 렌더 — 설계 의도) |

**현재 살아있는 시그널 = 자칭(자체사이트 정제) + 블로그(카카오 place앵커) + 후기(카카오).**
→ 즉 4시그널 중 **3축**으로 도는 상태. Vision·네이버가 들어오면 교차 검증이 더 단단해지고 "확실" 등급이 는다.

> 이미지 자체는 자체사이트 크롤 시 수집됨(`SITE#IMAGES`/S3, 평균 21장/병원) — **분석(Vision)** 만 미실행.
> 즉 "이미지 미수집"이 아니라 "이미지 분석 미실행"이다.
