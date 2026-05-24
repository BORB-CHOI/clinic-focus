# ai/ — AI · RAG 트랙

clinic-focus의 AI·RAG 모듈. 병원 크롤링 데이터를 받아 **4 시그널 교차 검증으로
주력 분야를 분류**하고, **자연어 통합 설명을 생성**하며, **S3 Vectors 기반
검색**을 제공한다.

> 운영 규칙·프롬프트 원칙은 [`CLAUDE.md`](./CLAUDE.md), 함수 명세는
> [`../docs/API-BE-AI.md`](../docs/API-BE-AI.md) 참조.
> 이 README는 "지금 무엇이 되어 있고 어떻게 확인하나"에 집중한다.

## 이건 서버가 아니다

`ai/`는 **순수 Python 라이브러리**다. 자체 서버·포트·FastAPI 앱이 없다.
BE가 같은 EC2 프로세스 안에서 함수로 직접 import해서 쓴다.

```python
from ai import classify_hospital, generate_description
```

→ AI 파트를 "구동"한다는 건 서버를 띄우는 게 아니라 **함수를 호출하거나
테스트를 돌리는 것**이다.

## 현재 상태 (2026-05-20)

### 구현 완료 — 공개 함수 전부

| 함수 | 파일 | 역할 |
| --- | --- | --- |
| `classify_hospital` | `pipeline/classify.py` | 4 시그널 교차 검증 분류 + 신뢰도 |
| `generate_description` ⭐ | `pipeline/describe.py` | 자연어 통합 설명 (의료법 5규칙) |
| `extract_services_and_doctors` | `pipeline/extract.py` | 진료 항목·의료기기·의료진 추출 |
| `analyze_images` | `pipeline/vision.py` | Bedrock Vision + Textract |
| `embed_text` | `search/embed.py` | Titan Embed v2 (1024차원) |
| `index_hospital` / `index_hospital_with_meta` | `search/vector_store.py` | S3 Vectors 적재 |
| `search_similar` | `search/vector_store.py` | 자연어·위치·복합 검색 |
| `find_related_hospitals` | `search/related.py` | 같은 주력 + 빈자리 보완 추천 |
| `recompute_confidence` / `aggregate_feedback_stats` | `search/feedback.py` | 피드백 반영 |

> **2026-05-20 수정 완료** — `generate_description`의 프롬프트 버그 2건:
> (1) 템플릿 파일 경로가 `ai/pipeline/prompts/`를 가리키던 문제,
> (2) 템플릿의 JSON 예시 중괄호 때문에 `str.format()`이 `KeyError`로 깨지던 문제.

### 남은 작업 / 알려진 문제

- **테스트 0개** — `ai/tests/` 디렉터리 자체가 없음. `CLAUDE.md`가 의무화한
  Bedrock mock 기반 테스트 미작성.
- **후기 시그널 stub** — `_analyze_reviews()`가 항상 빈 `ReviewSignal` 반환
  (BE가 아직 후기를 수집하지 않음).
- **과목별 프롬프트 미분리** — `prompts/hospital_description.md` 1개만 존재.
  CLAUDE.md는 진료과목별 분리를 권장.
- **BE 픽스처 스키마 불일치** — `be/tests/fixtures/sample_hospital.json`의
  `public_data`에 `name`·`address`·`phone`·`lat`·`lng`가 있는데 `PublicData`
  모델은 `extra="forbid"`라 그대로 로드하면 검증 실패. BE 트랙에 확인 필요.

## 파일별 설명

### 루트 (`ai/`)

| 파일 | 설명 |
| --- | --- |
| `__init__.py` | BE에 노출하는 공개 인터페이스. boto3 미설치 환경에서도 import되도록 lazy import |
| `requirements.txt` | 의존성 — boto3 · botocore · pydantic |
| `CLAUDE.md` | AI 트랙 작업 규칙 (에이전트용 컨텍스트) |
| `README.md` | 이 문서 (사람용 — 현재 상태·검증 방법) |

### `core/` — 공통 인프라

| 파일 | 설명 |
| --- | --- |
| `bedrock_client.py` | Bedrock 호출 래퍼 — `invoke_model`(텍스트) · `invoke_model_with_image`(Vision) |
| `exceptions.py` | 도메인 예외 8종 (`BedrockInvocationError` · `DescriptionValidationError` 등) |

### `pipeline/` — 분류 · 설명 · 추출 · Vision

| 파일 | 설명 |
| --- | --- |
| `classify.py` | `classify_hospital` — 4 시그널 교차 검증, 자칭 도배 페널티, 신뢰도 점수 산출 |
| `describe.py` | `generate_description` — 자연어 통합 설명, 의료법 5규칙 강제 + 재시도 검증 |
| `extract.py` | `extract_services_and_doctors` — 진료 항목 · 다루지 않는 분야 · 기기 · 의료진 추출 |
| `vision.py` | `analyze_images` — Bedrock Vision 이미지 분석 + Textract OCR 보조 |

### `prompts/`

| 파일 | 설명 |
| --- | --- |
| `hospital_description.md` | `generate_description` 프롬프트 템플릿 (의료법 5규칙 · 출력 JSON 스키마) |

### `search/` — 임베딩 · 벡터 · 추천 · 피드백

| 파일 | 설명 |
| --- | --- |
| `embed.py` | `embed_text` — Titan Embed v2 호출, 1024차원 벡터 |
| `vector_store.py` | `index_hospital` · `search_similar` — S3 Vectors 적재·검색 (자연어/위치/복합 모드) |
| `related.py` | `find_related_hospitals` — 같은 주력 + 빈자리 보완 병원 추천 |
| `feedback.py` | `aggregate_feedback_stats` · `recompute_confidence` — 피드백 집계 · 신뢰도 재계산 |

### `scripts/`

| 파일 | 설명 |
| --- | --- |
| `smoke_test.py` | 실연동 스모크 테스트 — 실제 Bedrock 호출로 핵심 3개 함수 검증 |

> 각 디렉터리의 `__init__.py`는 패키지 마커 (대부분 빈 파일).

## 데이터는 어디에 (BE와의 경계)

AWS 계정이 둘로 나뉜다 — AI 서비스(Bedrock·S3 Vectors·Textract)는 **개인 계정**,
정형 데이터·원본 저장은 **지원 계정**(us-east-1)에 있다. 별도 "AI 전용 DB"는 없다.

| 저장소 | 계정 | 소유 | AI의 접근 |
| --- | --- | --- | --- |
| DynamoDB | 지원 | BE | `aggregate_feedback_stats`·`recompute_confidence`가 boto3로 직접 read |
| S3 Vectors | 개인 | AI | `index_hospital` / `search_similar`가 read·write |
| S3 (원본 HTML·이미지) | 지원 | BE | `analyze_images`가 `s3://` 이미지 read |

분류·설명 결과(`Classification`·`HospitalDescription` 등)는 AI가 Pydantic
객체로 **반환만** 하고, DynamoDB 저장은 BE 책임이다. 예외는 위 피드백
함수 2개 — AI가 DynamoDB를 직접 읽는다.

## 결과 확인하기

`ai/`는 서버가 아니므로 "구동"이 아니라 함수 호출·테스트로 확인한다.
두 가지 경로가 있다.

### A. AWS 없이 — mock 테스트 (비용 0)

모든 Bedrock 호출이 mock 가능하게 설계됐다. import 동작만 빠르게 보려면:

```bash
python -c "import ai; print(ai.__all__)"
```

함수 로직은 `@patch`로 Bedrock 응답을 가짜로 주입해 검증한다:

```python
from datetime import datetime
from unittest.mock import patch

from ai import classify_hospital
from shared.models import CrawlData, CrawledPage, PublicData


@patch("ai.core.bedrock_client.invoke_model")
def test_classify(mock_invoke):
    mock_invoke.return_value = {
        "content": [{"type": "text",
                     "text": '{"keywords":["아토피"],'
                             '"primary_focus":["일반 진료(아토피·여드름)"],'
                             '"spam_score":0.1}'}]
    }
    crawl = CrawlData(
        hospital_id="h1", website_url="https://x.kr",
        pages=[CrawledPage(url="https://x.kr", page_type="main",
                           html_text="아토피 여드름 진료 안내",
                           fetched_at=datetime(2026, 5, 1))],
        images=[],
        public_data=PublicData(license_number="h1", specialists=[],
                               registered_devices=[]),
    )
    result = classify_hospital(crawl, use_vision=False)
    assert result.confidence.level in ("확실", "추정", "정보 부족")
```

AWS 없이 검증 가능한 것: 4 시그널 교차검증 수학, 자칭 도배 페널티, 신뢰도
점수·등급, haversine 거리, JSON 파싱, 의료법 5규칙 검증, 검색 모드 분기.

> `ai/tests/`는 아직 비어 있다. 위 패턴으로 채워야 한다 (CLAUDE.md 의무사항).

### B. 실연동 — 스모크 테스트 (실제 Bedrock 호출)

```bash
python ai/scripts/smoke_test.py
```

`embed_text` → `classify_hospital` → `generate_description` 순으로 실제
Bedrock을 호출하고 단계별 PASS/FAIL을 출력한다. 이 세 함수는 Bedrock(개인
계정)만 쓰므로 개인 계정 자격증명만 있으면 로컬에서도 검증된다. 사전 조건:

1. 개인 계정 자격증명 설정 — `aws configure`(기본 프로파일) 또는 `AWS_PROFILE` 환경변수
2. `us-east-1`에서 모델 액세스 활성화 (Bedrock 콘솔):
   `us.anthropic.claude-sonnet-4-5-20250929-v1:0`,
   `amazon.titan-embed-text-v2:0`

S3 Vectors 적재·검색과 DynamoDB를 쓰는 함수는 스모크 범위에서 제외했다.
지원 계정 서비스(DynamoDB 등)는 Access Key를 못 받으므로 EC2(VSCode Remote-SSH)의
인스턴스 프로파일 환경에서 검증한다.

## 환경 변수

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `AWS_REGION` | `us-east-1` | Bedrock·S3 Vectors 리전 (개인 계정) |
| `BEDROCK_LLM_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | LLM·Vision |
| `BEDROCK_EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` | 임베딩 |
| `S3_VECTOR_BUCKET` | 환경별 | 벡터 버킷 (미설정 시 `S3VectorsError`) |
| `S3_VECTOR_INDEX` | `hospital-index` | 벡터 인덱스 이름 |
| `MAX_VISION_IMAGES` | `10` | 분류 1회 최대 Vision 이미지 수 |
| `CONFIDENCE_THRESHOLD_HIGH` | `95` | "확실" 등급 임계치 |
| `CONFIDENCE_THRESHOLD_LOW` | `70` | "정보 부족" 등급 임계치 |

## 의존성

`boto3` · `botocore` · `pydantic` ([`requirements.txt`](./requirements.txt)).
BE와 같은 EC2 프로세스에서 함께 실행된다.
