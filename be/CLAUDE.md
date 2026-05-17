# be/ — 백엔드 트랙 (김경재)

상위 컨텍스트는 `../CLAUDE.md`, FE 인터페이스는 `../.claude/docs/API-FE-BE.md`, AI 함수 호출은 `../.claude/docs/API-BE-AI.md`.

## 스택

| 항목 | 선택 |
|---|---|
| 언어 | Python 3.11+ |
| 프레임워크 | FastAPI + Mangum (Lambda 어댑터) |
| 데이터 검증 | Pydantic (모델은 `../shared/models.py`에 정의) |
| AWS SDK | boto3 |
| 크롤링 | httpx + BeautifulSoup4 (JS 렌더링은 Playwright Lambda Layer로 보강) |
| 배포 | AWS SAM (zip, 도커 안 씀) |

## 엔드포인트 (4개)

| 경로 | 용도 |
|---|---|
| `GET /api/search` | 자연어 + 위치 검색. 둘 중 최소 하나 필수 |
| `GET /api/hospitals/{id}` | 상세 페이지 9개 영역 데이터 통합 응답. ⭐ 핵심 |
| `GET /api/hospitals/{id}/history` | 분류 변경 이력 |
| `POST /api/feedback` | 익명 피드백 제출 (디바이스ID 기반 중복 방지) |

응답 스키마는 `../.claude/docs/API-FE-BE.md`의 공통 데이터 타입 + 엔드포인트 섹션을 그대로 따른다.

## AI 모듈 호출

같은 Lambda zip에 들어있으므로 Python import로 호출 — **HTTP 호출 아님**:

```python
from ai import (
    classify_hospital,
    generate_description,
    extract_services_and_doctors,
    find_related_hospitals,
    aggregate_feedback_stats,
    search_similar,
    index_hospital,
    recompute_confidence,
)
from shared.models import CrawlData, SearchQuery
```

함수 시그니처·예외·동작 흐름은 `../.claude/docs/API-BE-AI.md` 참조. 추후 분리하더라도 시그니처가 그대로 HTTP body 스키마가 되므로 호출 코드만 바꾸면 됨.

## 새 병원 등록 파이프라인

`be/handlers/index_hospital.py`의 흐름:

1. 크롤링 데이터 로드 (S3 + DynamoDB)
2. `classify_hospital(crawl_data)` → `Classification`
3. `extract_services_and_doctors(...)` → 진료 항목·다루지 않는 분야·기기·의사
4. `generate_description(...)` → AI 통합 설명 ⭐
5. `find_related_hospitals(...)` → 같은 주력 + 빈자리 보완
6. DynamoDB 적재
7. `index_hospital(...)` → S3 Vectors 임베딩 (대상: AI 설명 본문)

## DynamoDB 테이블

`Hospitals` / `Classifications` / `Signals` / `Confidence` / `Feedback` / `ChangeHistory` / `HospitalDescriptions`. 파티션 키·GSI는 분류 스키마 v1 동결 후 확정.

위치 기반 검색은 S3 Vectors 메타데이터의 `lat`/`lng`로 bounding box 1차 필터 → Lambda haversine 정확 계산.

## 응답 포맷

성공: `{"data": {...}, "meta": {...}}`  
에러: `{"error": {"code": "...", "message": "...", "details": ...}}`

표준 에러 코드는 `../.claude/docs/API-FE-BE.md` "표준 에러 코드" 표 참조.

## CORS

FastAPI 미들웨어에서 CloudFront 도메인 + `http://localhost:5173` 허용. methods: `GET, POST`.

## 환경 변수

| 변수 | 기본값 |
|---|---|
| `AWS_REGION` | `ap-northeast-2` |
| `BEDROCK_LLM_MODEL_ID` | `anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` |
| `S3_VECTOR_BUCKET` / `S3_VECTOR_INDEX` | 환경별 |

## 작업 원칙

- 단일 Lambda zip 가정. 함수 분리는 트래픽 늘었을 때 고민 (PoC는 모놀리식이 효율적)
- 크롤링은 robots.txt 준수 + User-Agent 명시 + 요청 간격 조절
- 인증 없음 (PoC). 호출 제한은 API Gateway throttling 기본값
