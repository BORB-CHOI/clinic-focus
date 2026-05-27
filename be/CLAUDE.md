# be/ — 백엔드 트랙 (김경재)

상위 컨텍스트는 `../CLAUDE.md`, FE 인터페이스는 `../docs/API-FE-BE.md`, AI 함수 호출은 `../docs/API-BE-AI.md`.

## 스택

| 항목 | 선택 |
|---|---|
| 언어 | Python 3.11+ |
| 프레임워크 | FastAPI + uvicorn (EC2) |
| 데이터 검증 | Pydantic (모델은 `../shared/models.py`에 정의) |
| AWS SDK | boto3 |
| 크롤링 | httpx + BeautifulSoup4 (JS 렌더링은 Playwright로 보강) |
| 배포 | EC2 (git pull, 도커 안 씀) |

## 엔드포인트 (4개)

| 경로 | 용도 |
|---|---|
| `GET /api/search` | 자연어 + 위치 검색. 둘 중 최소 하나 필수 |
| `GET /api/hospitals/{id}` | 상세 페이지 9개 영역 데이터 통합 응답. ⭐ 핵심 |
| `GET /api/hospitals/{id}/history` | 분류 변경 이력 |
| `POST /api/feedback` | 익명 피드백 제출 (디바이스ID 기반 중복 방지) |

응답 스키마는 `../docs/API-FE-BE.md`의 공통 데이터 타입 + 엔드포인트 섹션을 그대로 따른다.

## AI 모듈 호출

같은 EC2 프로세스에서 도므로 Python import로 호출 — **HTTP 호출 아님**:

```python
from ai import (
    classify_hospital,
    generate_description,
    extract_services_and_doctors,
    find_related_hospitals,
    aggregate_feedback_stats,
    retrieve_hospital,           # 자연어 검색 (KB Retrieve 경유). 옛 search_similar 폐기
    ingest_hospital,             # KB DataSource 적재. 옛 index_hospital 폐기
    recompute_confidence,
)
from shared.models import CrawlData, SearchQuery, HospitalIngestMetadata
```

함수 시그니처·예외·동작 흐름은 `../docs/API-BE-AI.md` 참조. 추후 분리하더라도 시그니처가 그대로 HTTP body 스키마가 되므로 호출 코드만 바꾸면 됨.

## 새 병원 등록 파이프라인

`be/handlers/ingest_hospital.py`의 흐름:

1. 크롤링 데이터 로드 (S3 + DynamoDB)
2. `classify_hospital(crawl_data)` → `Classification`
3. `extract_services_and_doctors(...)` → 진료 항목·다루지 않는 분야·기기·의사
4. `generate_description(...)` → AI 통합 설명 ⭐
5. `find_related_hospitals(...)` → 같은 주력 + 빈자리 보완
6. DynamoDB 적재
7. `ingest_hospital(...)` → Bedrock KB DataSource S3 업로드 (배치 시 trigger_ingestion=False, 마지막에 한 번만 ingestion job 트리거)

## DynamoDB 테이블

### 왜 DynamoDB

RDS도 가용했지만 우리 access pattern과 워크로드가 DDB에 맞음:

- **본문은 S3, 메타는 DDB** — `CrawlData` 본문(~1MB+)을 S3에 두고 `hospital_id`로만 인덱싱하는 게 DDB의 정석 패턴. RDS면 BLOB 칼럼이 비대해짐
- **Single-table-design** — `PK=hospital_id` 하나로 한 병원의 모든 entity(메타·크롤링·분류·설명)를 `Query` 1회. RDS면 JOIN + N+1
- **Idle $0** — 크롤링 + 시연 외엔 트래픽 없음. RDS `db.t4g.micro` ~$13/월이 부담
- **스키마 자유** — `shared/models.py` 자주 바뀜. 마이그레이션 없는 게 큼
- **SQL 강점 무의미** — 자연어 검색 = Bedrock KB, 카테고리 필터 = GSI 1개. 복합 WHERE·JOIN 쓸 일 없음

자세한 비교·솔직한 한계는 `../docs/dev-roadmap.md` "왜 DynamoDB인가 (RDS 대신)" 섹션 참조.

### 스키마 — V2 single-table

[`be/adapters/dynamo_adapter.py`](adapters/dynamo_adapter.py) 가 가정하는 구조. **테이블은 콘솔에서 수동 생성** (SafeRole 에 `dynamodb:CreateTable` 권한 없음 — 절차는 [`../docs/setup/aws-onboarding.md`](../docs/setup/aws-onboarding.md) Step 6).

```
PK = hospital_id (S)
SK = entity      (S)

entity 종류 (한 병원 = 여러 row):
  META · CLASSIFICATION · DESCRIPTION · SERVICES · RELATED
  FEEDBACK#{device_id}#{ts} · HISTORY#{iso}
  SITE#PAGES · SITE#IMAGES
  NAVER#PLACE · NAVER#PLACE#REVIEWS · NAVER#BLOG
  KAKAO#PLACE · KAKAO#REVIEWS
  GOOGLE#PLACE · GOOGLE#REVIEWS
  PUBLIC#DEVICES · PUBLIC#DOCTORS
  VISION#RESULTS · INGEST#STATE
```

GSI 2개 (모두 sparse — META 항목만 인덱싱 키 채움):

| GSI | PK | SK | 용도 |
|---|---|---|---|
| `sigungu-specialty-index` | `sigungu_specialty` (S `"강남구#피부과"`) | `confidence_score` (N desc) | 카테고리 탐색 (BE 직접) |
| `geo-index` | `geohash_prefix` (S) | `lat_lng` (S `"{lat}#{lng}"`) | 지도 근처 검색 (Phase D 진입 후) |

- **한 병원의 모든 entity 1회 Query** — `query_hospital_entities(hospital_id)` 가 PK eq 로 다 모음
- **분류 완료 시 META 의 GSI 키 patch** — `save_classification` 이 `sigungu_specialty`·`confidence_score` 를 META 에 denormalize → sigungu-specialty-index 등장 시작
- **테이블 이름**: BE=`kmuproj-02-team3-backend`, AI=`kmuproj-10-clinic-Main` (계정 분리, 2026-05-25)
- **상세 entity 표·BE 운영본 호환**: [`../docs/plans/task-queue.md`](../docs/plans/task-queue.md) §3

### 검색 경로 이원화

자연어 검색은 AI 모듈 `retrieve_hospital`이 KB Retrieve로 처리하고, 단순 카테고리 탐색(`sigungu=강남구 & specialty=피부과` 전체 목록)은 BE가 DynamoDB GSI로 직접 처리 (`sigungu#specialty` 같은 복합 키). 위치 기반 검색은 KB 메타필터(`lat`/`lng` bounding box) + EC2 haversine 재계산.

## 응답 포맷

성공: `{"data": {...}, "meta": {...}}`  
에러: `{"error": {"code": "...", "message": "...", "details": ...}}`

표준 에러 코드는 `../docs/API-FE-BE.md` "표준 에러 코드" 표 참조.

## CORS

FastAPI 미들웨어에서 CloudFront 도메인 + `http://localhost:5173` 허용. methods: `GET, POST`.

## 환경 변수

| 변수 | 기본값 |
|---|---|
| `AWS_REGION` | `us-east-1` |
| `BEDROCK_LLM_MODEL_ID` | (지원) `anthropic.claude-haiku-4-5-...` / (개인 Vision) `global.anthropic.claude-sonnet-4-6` |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` |
| `KB_ID` / `KB_DATA_SOURCE_ID` | `GTBJ6HLFDK` / `PLC6QYALDU` (강사 제공 `kmuproj-team-03`) |
| `KB_DATASOURCE_S3_BUCKET` / `KB_DATASOURCE_S3_PREFIX` | (강사 제공) — `get-data-source`로 확인 |

> Bedrock KB · Bedrock(Haiku/Nova) · Titan · DynamoDB · S3는 **지원 계정**, Sonnet 4.6(Vision 시연)만
> **개인 계정** (서울 리전 `ap-northeast-2`)에 있다. 자세한 건 `../CLAUDE.md`의 "AWS 계정·인프라 구조" 참조.

## 작업 원칙

- 단일 EC2 프로세스 가정. 분리는 트래픽 늘었을 때 고민 (PoC는 모놀리식이 효율적)
- 크롤링은 robots.txt 준수 + User-Agent 명시 + 요청 간격 조절
- 인증 없음 (PoC). 호출 제한은 API Gateway throttling 기본값
