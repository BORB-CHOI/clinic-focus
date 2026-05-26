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

### ERD — 7-table 가정 (AI 트랙 사용 형태)

코드(`be/scripts/setup_dynamodb.py`, `be/adapters/dynamo_adapter.py`)와 AI 트랙 자기 계정(`kmuproj-10-clinic-*`)이 따르는 구조. PK/SK 전부 String.

```
┌─────────────────────────────────────────────────────────┐
│ Hospitals                                               │
│   PK: hospital_id                                       │
│   attrs: name, location{sido,sigungu,address,lat,lng},  │
│          phone, website_url, standard_specialty, ...    │
│                                                         │
│   GSI: sigungu-index                                    │
│     PK: sigungu  → Projection: ALL                      │
│     용도: list_hospitals_by_sigungu (카테고리 탐색)     │
└─────────────────────────────────────────────────────────┘
        │ hospital_id (논리적 FK, 명시 관계 없음)
        ├─────────────────┬─────────────────┬──────────┐
        ▼                 ▼                 ▼          ▼
┌──────────────────┐ ┌──────────────────┐ ┌─────────┐ ┌──────────────────┐
│ Classifications  │ │HospitalDescript- │ │Services │ │ RelatedHospitals │
│ PK: hospital_id  │ │ions              │ │AndDoctors│ │ PK: hospital_id │
│ attrs: standard_ │ │ PK: hospital_id  │ │PK: hosp.│ │ attrs: same_focus│
│   specialty,     │ │ attrs: ai_desc,  │ │_id      │ │   [], gap_fill[] │
│   primary_focus, │ │   generated_at,  │ │attrs:   │ │                  │
│   confidence,    │ │   source_tags    │ │ services│ │                  │
│   signals{...}   │ │                  │ │ [], doc-│ │                  │
└──────────────────┘ └──────────────────┘ │ tors[], │ └──────────────────┘
                                          │ devices │
                                          └─────────┘
        │
        ├─────────────────┐
        ▼                 ▼
┌──────────────────┐ ┌──────────────────────────┐
│ Feedback         │ │ ChangeHistory            │
│ PK: hospital_id  │ │ PK: hospital_id          │
│ SK: feedback_id  │ │ SK: changed_at (ISO8601) │
│ attrs: device_id,│ │ attrs: field, old, new,  │
│   thumb (👍/👎), │ │   reason, signal_source  │
│   timestamp      │ │                          │
└──────────────────┘ └──────────────────────────┘
```

- **관계는 DDB에 명시 안 됨** — `hospital_id` 동일성으로만 연결. JOIN은 코드에서 (`Hospitals.get` + `Classifications.get` 등 병렬 호출)
- **GSI는 `Hospitals.sigungu-index` 1개** — `list_hospitals_by_sigungu`([be/adapters/dynamo_adapter.py:71](../be/adapters/dynamo_adapter.py#L71))가 유일한 비-PK 쿼리
- **SK가 있는 테이블 2개** — `Feedback` (한 병원 여러 피드백), `ChangeHistory` (시간순 이력)
- **테이블 prefix**: BE=`kmuproj-02-clinic-`, AI=`kmuproj-10-clinic-` (계정 분리, 2026-05-25)

### BE 실 운영 분기 — Single-table

위 7-table은 **코드 가정**이고, BE 담당자(김경재)는 실제 `kmuproj-02-team3-backend` **단일 테이블**로 운영 중 (확인: 3,124 items, PK=`hospital_id`+SK=`entity`). entity 값으로 `META`/`CRAWL`/`CLASSIFICATION`/... 를 구분해서 한 테이블에 통합. AI 트랙은 7-table 가정 유지 (PoC 범위 + 분담), single-table 전환 동기화는 BE가 판단.

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
