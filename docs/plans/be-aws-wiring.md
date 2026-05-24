# BE 트랙 AWS 연결 — 작업 큐 & 의존성 매트릭스

> 작성: 2026-05-24 · 담당: 김경재
>
> KB DataSource S3 권한이 강사한테 묶여 있는 상황에서, **지금 바로 진행 가능한
> AWS 연결**을 분리해 정리한다. KB·`kmuproj-02-vector` 권한 대기 항목은
> 별도 섹션으로 분리.

---

## TL;DR — 오늘 밤~내일 바로 할 수 있는 것

1. **DynamoDB 7개 테이블 생성** (`python be/scripts/setup_dynamodb.py`) — 권한 OK
2. **HIRA → DynamoDB 5개 구 1만 적재** (`python be/scripts/load_seoul_5gu.py`) — `HIRA_API_KEY` 발급 후
3. **자체 S3 버킷(`kmuproj-10-*`) 생성 후 `S3Adapter` 진짜 S3로 전환** — 현재는 로컬 파일시스템 어댑터
4. **풀크롤링 1만건 실행** (`python be/scripts/crawl_all.py`) — DynamoDB scan → S3 적재

KB ingest(`feat/be/clean-noise` 다음 단계)는 강사 권한 받기 전까지 보류.

---

## 작업 진행 가능 매트릭스

| # | 작업 | AWS 자원 | 권한 상태 | 의존성 | 추정 시간 |
|---|------|---------|----------|--------|----------|
| **B1** | DynamoDB 7테이블 생성 | DynamoDB (지원) | ✅ OK | 없음 | 5분 |
| **B2** | HIRA API 키 발급 신청 | 공공데이터포털 | ⏳ 외부 | 없음 | 신청 후 1~2일 |
| **B3** | 서울 5개구 1만 메타 적재 | DynamoDB | ✅ OK | B1, B2 | 30분 |
| **B4** | 자체 S3 버킷 생성 (`kmuproj-10-clinic-focus-crawl`) | S3 (지원) | ✅ OK (자기 prefix) | 없음 | 5분 |
| **B5** | S3Adapter를 boto3 진짜 S3로 전환 | S3 (지원) | ✅ OK | B4 | 1~2시간 |
| **B6** | crawl_results 28개 → S3 마이그레이션 | S3 | ✅ OK | B5 | 10분 |
| **B7** | 풀크롤링 1만건 실행 | DynamoDB scan + S3 put | ✅ OK | B3, B5 | 4~8시간 (실행만, 모니터링 동안 다른 일 가능) |
| **B8** | 페이지 단위 본문 정제 (잡음 60% 제거) | — (순수 로직) | — | B6 (샘플 검증용) | 4~6시간 |
| **B9** | content_hash + crawled_at 컬럼 추가 (Hospitals) | DynamoDB | ✅ OK | B1 | 1시간 |
| **B10** | SQS 큐 2개 생성 (`ClinicFocusCrawlQueue`, `ClinicFocusIndexQueue`) | SQS (지원) | ✅ OK 추정 (Step 1에서 미검증 — 확인 필요) | 없음 | 10분 |
| **B11** | ai `index_hospital` → `ingest_hospital` rename 흡수 | — | — | AI PR #1 머지 후 | 30분 |
| **B12** | KB DataSource S3 권한 확보 | S3 (`kmuproj-02-vector`) | 🚧 강사 대기 | — | 외부 |
| **B13** | `feat/be/test-fix` (mock_adapters 버그) | — | — | 없음 | 30분 |

진행 가능: B1, B2, B4, B5, B6, B8, B9, B10, B13  
의존 대기: B3(←B2), B7(←B3·B5), B11(←AI PR #1), B12(←강사)

---

## 의존성 그래프

```
B2 (HIRA Key)         B4 (S3 버킷 생성)         B10 (SQS 큐)
   │                       │                       │
   ▼                       ▼                       │
B1 (DDB 테이블) ─── B3 (1만 메타 적재)            │
   │                       │                       │
   ▼                       │                       │
B9 (hash 컬럼)             │                       │
                           ▼                       │
              ┌──── B5 (S3Adapter 전환)            │
              │            │                       │
              │            ▼                       │
              │     B6 (28개 마이그레이션)         │
              │            │                       │
              │            ▼                       │
              └──── B7 (풀크롤링 1만) ◀──────────┘ (선택: SQS 분산)
                           │
                           ▼
                    B8 (잡음 정제)
                           │
                           ▼
                    [AI 트랙 #4 룰 분류]
                           │
                           ▼
                    B11 (ingest 함수 rename)
                           │
                           ▼
                    B12 (KB ingest, 권한 대기)
```

---

## 진행 가능 항목 상세

### B1. DynamoDB 7테이블 생성 ✅ 바로 가능

**상태**: 스크립트 완비 ([be/scripts/setup_dynamodb.py](../../be/scripts/setup_dynamodb.py)).

**실행**:
```bash
cd /home/ec2-user/clinic-focus
python be/scripts/setup_dynamodb.py
```

생성 대상:
- `Hospitals` (PK `hospital_id`, GSI `sigungu-index`)
- `Classifications` / `HospitalDescriptions` / `ServicesAndDoctors` / `RelatedHospitals` (PK `hospital_id`)
- `Feedback` (PK `hospital_id`, SK `feedback_id`)
- `ChangeHistory` (PK `hospital_id`, SK `changed_at`)

전부 `BillingMode=PAY_PER_REQUEST`라 idle 비용 0.

**검증**:
```bash
aws dynamodb list-tables --region us-east-1
```

**리스크**:
- `ResourceInUseException`는 이미 만들어진 거라 무시 OK (스크립트가 catch).
- 다른 팀이 같은 이름으로 만들었으면 충돌 — `TABLE_PREFIX=kmuproj-10-` 같은 환경변수로 우회 가능. setup 스크립트가 prefix 반영 OK.

**검토 필요**: PoC라 prefix 안 붙여도 되는지 vs 팀 충돌 방지로 prefix 붙일지 — 일단 prefix 없이 진행, 충돌 발견 시 `TABLE_PREFIX=kmuproj-10-` 추가.

---

### B2. HIRA API 키 발급 ⏳ 외부 의존

**상태**: `.env.example`의 `HIRA_API_KEY=` 비어 있음.

**조치**: 공공데이터포털(data.go.kr)에서 "건강보험심사평가원 병원·약국 찾기서비스" 일반 인증키 신청. 평일 1~2일 소요.

**검증** (키 받은 후):
```bash
HIRA_API_KEY="..." python be/scripts/test_hira.py
```

`test_hira.py`는 이미 있음 — 동작 확인용.

---

### B3. 서울 5개구 1만 메타 적재 (B1·B2 의존)

**상태**: 스크립트 완비 ([be/scripts/load_seoul_5gu.py](../../be/scripts/load_seoul_5gu.py)).

대상: 강남(110001) · 마포(110014) · 성북(110017) · 서초(110018) · 송파(110020)

**실행**:
```bash
python be/scripts/load_seoul_5gu.py
```

각 구별 페이징 처리 + `HospitalMeta` 변환 + DynamoDB `put_item`. URL 보유 카운트도 같이 집계.

**예상 결과**: 5개구 합쳐 8천~1만 2천 건. URL 보유율 60~70% 예상 (성북구 28건 표본 기준).

---

### B4. 자체 S3 버킷 생성 ✅ 바로 가능

**상태**: 아직 안 만듦.

CLAUDE.md 규칙: 버킷명 `{username}-` 접두사. 본인 username이 `kmuproj-10`이므로:

```bash
aws s3 mb s3://kmuproj-10-clinic-focus-crawl --region us-east-1
aws s3 mb s3://kmuproj-10-clinic-focus-images --region us-east-1  # 이미지 별도 (선택)
```

검증:
```bash
aws s3 ls | grep kmuproj-10
```

권한: 자기 prefix(`kmuproj-10-*`) CreateBucket은 강사 정책에서 풀어줬을 가능성 높음. 실패 시 Step 1 권한 확인 항목에 추가하고 강사 문의.

---

### B5. S3Adapter를 boto3 진짜 S3로 전환 (B4 의존)

**상태**: 현재 [be/adapters/s3_adapter.py](../../be/adapters/s3_adapter.py)가 **로컬 파일시스템 어댑터**임. 파일명에 'S3'가 들어가 있지만 boto3 호출 0건.

**현 동작**: `CRAWL_DATA_DIR` 환경변수로 지정된 로컬 디렉토리에 JSON 저장.

**전환 방향**: 두 옵션 — 사용자가 선택할 항목.

| 옵션 | 설명 | 비고 |
|---|---|---|
| **A. 통째로 boto3 전환** | `save_crawl_data`/`load_crawl_data`/`save_raw_html`/`save_image` 전부 `s3.put_object` / `s3.get_object`로 교체 | 단순. 단점: 로컬 개발 시 매번 S3 왕복 |
| **B. 듀얼 모드** | `STORAGE_BACKEND=local|s3` env로 분기. 로컬은 dev/test, S3는 prod | 복잡도 증가. PoC엔 과함 |

**권장**: A. PoC 단순화 우선.

API:
```python
class S3Adapter:
    def __init__(self):
        self._client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        self._bucket = os.environ.get("S3_CRAWL_BUCKET", "kmuproj-10-clinic-focus-crawl")

    def save_crawl_data(self, hospital_id, data: CrawlData) -> str:
        key = f"crawl/{hospital_id}.json"
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data.model_dump_json(indent=2).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        return f"s3://{self._bucket}/{key}"
```

`.env.example`에 `S3_CRAWL_BUCKET` 추가.

**검토 필요**: 이미지를 S3에 저장할지(원본 보존) vs URL만 메타에 적재할지. 풀크롤링 1만 × 30 이미지 = 30만 파일이라 풍선처럼 커지면 비용·관리 부담. 일단 **URL만 메타에 적재**(현재 `CrawledImage.url`) — 실제 다운로드는 Vision 시연 10개에 한정해서 [be/scripts/download_images.py](../../be/scripts/download_images.py) 별도 트리거.

---

### B6. crawl_results 28개 → S3 마이그레이션 (B5 의존)

**상태**: `be/data/crawl_results/` 28개 JSON이 로컬에만 있음. AI 트랙이 정제 효과 검증에 활용 중.

**조치**: 일회성 스크립트 — 각 JSON 로드 → `S3Adapter.save_crawl_data` 호출.

```python
# be/scripts/migrate_local_crawl_to_s3.py
for path in glob("be/data/crawl_results/*.json"):
    data = CrawlData.model_validate_json(open(path).read())
    s3.save_crawl_data(data.hospital_id, data)
```

마이그레이션 후 task-queue.md의 "be/data/crawl_results 처리" 항목 닫음 (정제 검증 후 .gitignore 추가 → 삭제).

---

### B7. 풀크롤링 1만건 실행 (B3·B5 의존)

**상태**: 스크립트 완비 ([be/scripts/crawl_all.py](../../be/scripts/crawl_all.py)). DynamoDB scan → URL 있는 병원만 → 비동기 크롤링 → S3 적재.

**실행 전 검토**:
- 현재 스크립트의 `s3.load_crawl_data(hospital_id)` 중복 체크 — S3 전환 후에도 동작하는지 확인 (`get_object`로 404 잡아야 함)
- `await asyncio.sleep(0.5)` 호스트당 딜레이 OK, 단 같은 호스트에 여러 페이지 가는 건 `crawl_one_hospital` 내부의 `REQUEST_DELAY=1.0`로 처리됨
- robots.txt 미준수 — `User-Agent`는 박았는데 robots는 안 봄. PoC라 일단 두지만 운영 시 보강 필요

**비용 추정**: HTTP 요청 비용 0. DynamoDB scan 1회(1만 row) ~$0.02. S3 put 1만 × 50KB = 500MB Standard ~$0.01/월. **사실상 무료**.

**실행 시간**: 직렬 1만 × 5초(서브페이지 9개 × 0.5초) = ~14시간. **백그라운드 + 모니터링** 권장.

**개선 여지** (선택): `asyncio.Semaphore`로 호스트 단위 동시성 5~10 정도 — 시간 ½~⅙로 단축. 단 호스트 폭주 위험. PoC라 직렬 그대로 가도 됨.

**검토 필요**: 한 번에 전체 vs 구 단위 분할 — 실패 격리·재시도 편의는 구 단위 분할이 유리. 일단 전체 1회 실행해보고 실패율 보고 결정.

---

### B8. 페이지 단위 본문 정제 (잡음 60% 제거) (B6 의존)

**상태**: task-queue.md `#3 feat/be/clean-noise` 항목. AI 트랙이 28개 표본으로 잡음 60~70% 확인.

**작업** (task-queue.md 그대로 재기재):
- 페이지 간 중복 단락 자동 검출 (한 사이트에서 N회 반복되는 단락 = 푸터/메뉴 판정)
- 블랙리스트 단락 (modoo 안내·개인정보취급방침·환자권리장전·이용약관·비급여 고지문·404·Copyright)
- 정제 후 100자 미만 → "정보 부족" 분류 제외 마크
- 28개 비교 테스트 (전/후 토큰 수)

**중요**: 이건 풀크롤링 **전**에 끝내야 다시 재크롤링 안 함. 풀크롤링 결과에 잡음 60% 박혀서 적재되면 KB ingest 비용 + 룰 분류 정확도 양쪽 손해.

**대안**: 정제 로직을 크롤러에 박지 않고 **분류 직전 inline 처리**로 옮기면, 풀크롤링과 병렬 진행 가능. 권장.

```
crawler.py (원문 그대로 적재) ──→ S3
                                    │
                                    ▼
                              clean.py (정제) ──→ classify_rule.py
```

---

### B9. content_hash + crawled_at 컬럼 추가 (B1 의존)

**상태**: task-queue.md `#6 feat/be/hash-diff-foundation`. PoC 단계는 구조만 잡으면 OK.

**작업**:
- `HospitalMeta` 또는 `Hospitals` 테이블 항목에 두 컬럼:
  - `content_hash`: 정제된 본문 SHA-256 (병원 통합)
  - `crawled_at`: ISO8601
- 재크롤링 시 `content_hash` 비교 → 변경 시만 KB ingest 트리거(B12 이후)
- 스키마는 동적이라 setup 스크립트 변경 불필요 — 어댑터에서 컬럼만 추가하면 됨

**선택**: `shared/models.py`에 추가할지 vs DynamoDB only로 둘지 — 핵심 비즈니스 로직에 쓰일 거면 모델에 추가하는 게 깔끔.

---

### B10. SQS 큐 2개 생성 ✅ 바로 가능 (권한 확인 필요)

**상태**: `crawl_trigger.py` / `crawl_hospital.py`가 `INDEX_QUEUE` / `CRAWL_QUEUE` 가정. 큐 자체 생성 흔적 없음.

**조치**:
```bash
aws sqs create-queue --queue-name ClinicFocusCrawlQueue --region us-east-1
aws sqs create-queue --queue-name ClinicFocusIndexQueue --region us-east-1
```

**검증**: `aws sqs list-queues --region us-east-1`로 두 개 보이는지.

**검토 필요**: PoC 단일 EC2 모놀리식에서 SQS 정말 쓸지 — CLAUDE.md "단일 EC2 프로세스 가정. 분리는 트래픽 늘었을 때 고민" 원칙과 충돌할 수 있음. **권장: 일단 큐 미사용으로 `crawl_all.py` 직렬 실행. 큐 생성은 Phase 2로 미룸**.

→ 결정 위임: 김경재가 직접 판단. 이미 코드는 SQS 가정해서 짜여 있어서 만들기만 하면 동작.

---

### B11. ai `index_hospital` → `ingest_hospital` rename 흡수 (AI PR #1 머지 후)

**상태**: 현재 [be/handlers/index_hospital.py:13](../../be/handlers/index_hospital.py)가 `from ai import index_hospital` 호출. AI 트랙 PR #1(`feat/ai/aws-clients` 재재설계)에서 함수명 변경 예정.

**작업** (별도 PR `refactor/be/ai-kb-rename` 권장):
- `be/handlers/index_hospital.py` → 새 함수 `ingest_hospital(hospital_id, content_text, metadata, trigger_ingestion=False)` 시그니처에 맞춰 호출부 교체
- 파일명도 변경 고려: `index_hospital.py` → `ingest_hospital.py` (혼동 방지)
- import문에 `HospitalIngestMetadata` 추가 (shared/models.py에 신규 정의 예정 — AI 트랙과 조율 필요)

**의존성**: AI 트랙이 `ai/__init__.py`에 새 함수 export 완료해야 시작 가능. 동시에 가도 됨(시그니처 합의된 상태) — 머지 순서만 AI → BE.

---

### B12. KB DataSource S3 권한 확보 🚧 강사 대기

**상태**: task-queue.md Step 3 그대로. `kmuproj-02-vector` 버킷에 `s3:PutObject` 권한 없음.

**대응**: AI 트랙(최비성)이 Slack 보냈음. 받으면 B12 unblock → B11 PR 머지 후 KB ingest 파이프라인 가동.

---

### B13. feat/be/test-fix (기존 큐 #2) — 독립 진행 가능

**상태**: task-queue.md `#2` 그대로.

- `be/tests/harness/mock_adapters.py`: `h.sigungu` → `h.location.sigungu` 버그
- `ChangeRecord` → `ClassificationChange` import 명시화
- `be/api/search.py`: `SearchQuery` 미사용 import 제거
- `be/adapters/dynamo_adapter.py`: `import json` 미사용 제거
- `smoke_test`에 import 검증 추가

위 어떤 AWS 작업과도 의존 없음. 누군가 손 빈 시점에 빠르게 처리 가능.

---

## 권장 진행 순서 (사용자 결정 필요)

자기 직전 시점에 사용자가 자고 일어나면 다음 순서로 보면 됨:

1. **B13** (test-fix, AWS 의존 0, 30분) — 워밍업
2. **B1** (DynamoDB 테이블, 5분) — 권한 확인 겸
3. **B4** (S3 버킷 생성, 5분) — 권한 확인 겸
4. **B2** (HIRA Key 신청) — 신청만 해두고 대기
5. **B5** (S3Adapter 전환, 1~2시간) — HIRA Key 기다리는 동안
6. **B6** (28개 마이그레이션, 10분) — 정제 효과 검증 데이터 보존
7. **B9** (hash 컬럼 추가) + **B8** (정제 로직) 병렬
8. **B3** (1만 메타 적재) — HIRA Key 받은 직후
9. **B7** (풀크롤링 1만) — 백그라운드 장시간
10. **B10** (SQS) — 필요하다고 판단되면. 안 만들어도 모놀리식으로 가능
11. **B11** (rename 흡수) — AI PR #1 머지 후
12. **B12** (KB ingest) — 강사 권한 후

`feat/be/clean-noise`(B8), `feat/be/hash-diff-foundation`(B9), `feat/be/crawl-seoul-5gu-full`(B3+B7)는 task-queue.md `#3·#6·#7`에 이미 있는 작업. B4·B5는 신규 항목 — task-queue.md에 추가 필요.

---

## 비용 추정 (PoC 전체)

| 자원 | 한 달 비용 |
|------|----------|
| DynamoDB (PAY_PER_REQUEST, 1만건) | < $0.10 |
| S3 (Standard, 500MB) | $0.01 |
| EC2 (`t3.small`, 24/7) | ~$15 (지원 계정) |
| 크롤링 HTTP 트래픽 | $0 |
| 합계 | **사실상 무료** (EC2 외) |

KB ingest·임베딩·LLM/Vision은 별도 — 본 문서 범위 밖.

---

## 환경변수 추가 필요 (`.env.example`)

```bash
# 신규
S3_CRAWL_BUCKET=kmuproj-10-clinic-focus-crawl
TABLE_PREFIX=           # 필요 시 kmuproj-10- (팀 충돌 회피)
```

기존 변수는 `.env.example`에 있음(`AWS_REGION`, `KB_*`, `HIRA_API_KEY` 등).

---

## 검토 필요 사항 (사용자 결정 필요)

1. **DynamoDB 테이블 prefix** — 팀 충돌 회피 위해 `TABLE_PREFIX=kmuproj-10-` 붙일지 vs 그대로 갈지
2. **S3Adapter 전환 방식** — 통째로 boto3(A) vs 듀얼 모드(B)
3. **SQS 큐 생성 여부** — 모놀리식 직렬로 갈지 vs 큐 분산으로 갈지
4. **이미지 S3 저장 정책** — 1만 × 30장 전부 저장 vs Vision 시연 10개만 다운로드
5. **풀크롤링 동시성** — 직렬(~14h) vs Semaphore 5~10(~2h)
6. **정제 로직 위치** — 크롤러 inline vs 분류 직전 별도 단계
