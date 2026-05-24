---
inclusion: always
---

# 트랙별 개발 컨벤션

> 원본: `be/CLAUDE.md`, `fe/CLAUDE.md`, `ai/CLAUDE.md`, `shared/CLAUDE.md`

---

## BE 트랙 (`be/`)

**스택:** Python 3.11 · FastAPI + uvicorn · Pydantic · boto3 · httpx + BS4 · EC2

### 엔드포인트 4개

| 경로 | 용도 |
|---|---|
| `GET /api/search` | 자연어 + 위치 검색. q 또는 lat/lng 최소 하나 필수 |
| `GET /api/hospitals/{id}` | 상세 페이지 9개 영역 통합 응답 ⭐ 핵심 |
| `GET /api/hospitals/{id}/history` | 분류 변경 이력 |
| `POST /api/feedback` | 익명 피드백 제출 (device_id 기반 중복 방지) |

### DynamoDB 테이블

`Hospitals` / `Classifications` / `HospitalDescriptions` / `ServicesAndDoctors` / `RelatedHospitals` / `Feedback` / `ChangeHistory`

### 환경 변수 (BE)

| 변수 | 설명 |
|---|---|
| `AWS_REGION` | `us-east-1` (지원 계정) |
| `TABLE_PREFIX` | 테이블 이름 접두사 (기본 없음) |
| `CRAWL_DATA_DIR` | 크롤링 결과 로컬 경로 |
| `HIRA_API_KEY` | 심평원 공공 API 키 |
| `KAKAO_REST_API_KEY` | 카카오 로컬 검색 API |
| `NAVER_MAP_CLIENT_ID/SECRET` | 네이버 지도 API |
| `PORT` | API 서버 포트 (기본 8000) |

### 실행

```bash
python be/main.py
# 또는
python -m uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000
```

---

## FE 트랙 (`fe/`)

**스택:** TypeScript · React + Vite · Tailwind CSS + shadcn/ui · TanStack Query · React Router · 카카오맵 JS SDK

### 주요 화면

- 검색 결과 화면 (카드 리스트 + 지도 토글)
- 병원 상세 페이지 (9개 영역) ⭐ 핵심 화면
- 분류 변경 이력 페이지
- 1-tap 피드백 UI (익명, localStorage device_id)

### 타입 자동 생성

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
```

수동 타입 정의 금지. BE FastAPI OpenAPI 스펙에서 자동 생성.

---

## AI 트랙 (`ai/`)

**스택:** Python 3.11 · boto3 (bedrock-runtime, bedrock-agent-runtime, bedrock-agent, s3) · Pydantic

### 환경 변수 (AI)

| 변수 | 설명 |
|---|---|
| `AWS_REGION` | `us-east-1` (지원 계정 — 기본 세션) |
| `AI_AWS_PROFILE` | 개인 계정 프로파일명 (Sonnet Vision 시연 한정, 예: `personal`) |
| `AI_AWS_ACCESS_KEY_ID` / `AI_AWS_SECRET_ACCESS_KEY` | 개인 계정 액세스 키 (프로파일 대안) |
| `BEDROCK_LLM_MODEL_ID` | 지원: `anthropic.claude-haiku-4-5-...` / 개인: `anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` (KB가 자체 사용, `embed_text` 직접 호출용) |
| `KB_ID` | `GTBJ6HLFDK` (강사 제공 KB `kmuproj-team-03`) |
| `KB_DATA_SOURCE_ID` | `PLC6QYALDU` (`main-datasource`) |
| `KB_DATASOURCE_S3_BUCKET` / `KB_DATASOURCE_S3_PREFIX` | DataSource S3 경로 (강사 제공, `get-data-source`로 확인) |
| `MAX_VISION_IMAGES` | 분류 1회당 최대 이미지 수 (기본 10) |
| `CONFIDENCE_THRESHOLD_HIGH` | "확실" 등급 임계치 (기본 95) |
| `CONFIDENCE_THRESHOLD_LOW` | "정보 부족" 등급 임계치 (기본 70) |

### 계정 분리 원칙

- DynamoDB · S3 · Bedrock(Haiku/Nova/Titan) · **Bedrock Knowledge Base** (지원 계정) → EC2 인스턴스 프로파일 (기본 세션)
- Bedrock Sonnet 4.5 Vision 시연 (개인 계정) → `ai/core/aws_clients.py` 팩토리로 별도 세션

### Bedrock 테스트 모킹

```python
from unittest.mock import patch

@patch("ai.core.bedrock_client.get_bedrock_client")
def test_classify_mocked(mock_client):
    mock_client.return_value.invoke_model.return_value = {"body": ...}
```

실제 Bedrock 호출 없이 테스트. `AI_AWS_ACCESS_KEY_ID` 미설정 시 AWS 호출 테스트 스킵.

---

## shared/ 트랙

`shared/models.py`가 BE·AI 양쪽의 단일 진실. FE는 OpenAPI에서 자동 생성.

변경 시 반드시:
1. `shared/models.py` 수정
2. BE 측 코드 업데이트
3. AI 측 코드 업데이트
4. FE 타입 재생성 (`openapi-typescript`)
