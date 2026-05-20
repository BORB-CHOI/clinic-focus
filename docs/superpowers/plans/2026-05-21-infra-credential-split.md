# 인프라 정합: 리전·자격증명 분리·Mangum 제거·스키마 통합

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 모듈이 개인 계정(Bedrock/S3 Vectors/Textract)을 쓰고 BE 모듈이 지원 계정(DynamoDB)을 쓰도록 자격증명을 분리하고, EC2 uvicorn 배포에 맞게 Mangum·Lambda 잔재를 제거한다.

**Architecture:** 단일 EC2 프로세스에서 be/ + ai/ + shared/ 가 함께 돈다. boto3 클라이언트를 계정별로 분리하는 팩토리를 `ai/core/aws_clients.py` 하나에 집중시키고, 나머지 모듈은 그 팩토리를 호출한다. BE FastAPI 앱은 `be/main.py`에서 uvicorn으로 직접 실행한다.

**Tech Stack:** Python 3.11, boto3, FastAPI, uvicorn, DynamoDB, S3 Vectors, Bedrock

---

## 배경: 버그 목록 (코드 읽어서 확인한 것들)

| 파일 | 버그 |
|------|------|
| `ai/core/bedrock_client.py` | region `ap-northeast-2`, 모델 ID `anthropic.` (US 프로파일 아님) |
| `ai/search/embed.py` | region `ap-northeast-2` |
| `ai/search/vector_store.py` | region `ap-northeast-2` |
| `ai/pipeline/vision.py` | region `ap-northeast-2` (Textract·S3·Bedrock 모두), 기본 자격증명 사용 |
| `ai/search/feedback.py` | region `ap-northeast-2`, DynamoDB 는 지원 계정인데 AI 모듈에 같이 있음 |
| `be/adapters/dynamo_adapter.py` | region `ap-northeast-2`, `ChangeRecord` import (모델 없음) |
| `be/tests/harness/mock_adapters.py` | `ChangeRecord` import, `h.sigungu` (실제로는 `h.location.sigungu`) |
| `be/handlers/api.py` | Mangum import + `handler = Mangum(...)` |
| `be/handlers/index_hospital.py` | Lambda `handler(event, context)` 서명, SQS 이벤트 파싱 |
| `be/handlers/crawl_trigger.py` | Lambda `handler(event, context)` 서명 |
| `be/handlers/crawl_hospital.py` | Lambda `handler(event, context)` 서명 |
| `requirements.txt` | `mangum>=0.17.0` |
| `ai/__init__.py` export | `index_hospital` 은 위치 정보 없음 → S3 Vectors에 lat/lng 미기록 |

---

## 파일 변경 지도

| 파일 | 변경 종류 |
|------|----------|
| `ai/core/aws_clients.py` | **신규** — 계정별 boto3 세션 팩토리 |
| `ai/core/bedrock_client.py` | 수정 — 개인 계정 팩토리 사용, 리전·모델 ID 기본값 |
| `ai/search/embed.py` | 수정 — 개인 계정 팩토리 사용, 리전 기본값 |
| `ai/search/vector_store.py` | 수정 — 개인 계정 팩토리 사용, 리전, `index_hospital` 시그니처 통합 |
| `ai/search/feedback.py` | 수정 — 지원 계정 팩토리 사용, 리전 |
| `ai/pipeline/vision.py` | 수정 — 개인 계정 팩토리 사용, 리전 |
| `ai/__init__.py` | 수정 — `index_hospital` 시그니처 업데이트 |
| `shared/models.py` | 수정 — `ChangeRecord` 타입 alias 추가 (backwards compat) |
| `be/adapters/dynamo_adapter.py` | 수정 — 리전, `ChangeRecord` 픽스, sigungu denormalize |
| `be/tests/harness/mock_adapters.py` | 수정 — `ChangeRecord` 픽스, `sigungu` 접근 방식 |
| `be/handlers/api.py` | 수정 — Mangum 제거 |
| `be/handlers/index_hospital.py` | 수정 — Lambda 서명 제거, EC2 함수로 전환 |
| `be/handlers/crawl_trigger.py` | 수정 — Lambda 서명 제거 |
| `be/handlers/crawl_hospital.py` | 수정 — Lambda 서명 제거 |
| `be/main.py` | **신규** — uvicorn 진입점 |
| `requirements.txt` | 수정 — `mangum` 제거 |
| `template.yaml` | **삭제** — SAM 미사용 |
| `be/scripts/setup_dynamodb.py` | **신규** — DynamoDB 테이블 생성 스크립트 (지원 계정) |
| `ai/scripts/setup_vectors.py` | **신규** — S3 Vectors 버킷/인덱스 생성 스크립트 (개인 계정) |
| `.env.example` | **신규** — 환경변수 템플릿 |

---

## Task 1: `ai/core/aws_clients.py` — 계정별 boto3 세션 팩토리

**Files:**
- Create: `ai/core/aws_clients.py`

이 파일이 모든 boto3 클라이언트의 단일 진입점이다. 다른 AI 모듈은 여기서만 클라이언트를 가져온다.

- [ ] **Step 1: 파일 생성**

```python
"""
ai/core/aws_clients.py — 계정별 boto3 세션 팩토리.

EC2 환경에서 두 개의 AWS 계정을 다룬다:
  - 지원 계정: EC2 인스턴스 프로파일로 자동 인증 (DynamoDB, S3)
  - 개인 계정: AI_AWS_* 환경변수로 명시적 인증 (Bedrock, S3 Vectors, Textract)

모든 AI 모듈은 이 팩토리를 통해서만 boto3 클라이언트를 만든다.
"""
from __future__ import annotations

import os

import boto3

# ---------------------------------------------------------------------------
# 개인 계정 세션 (Bedrock · S3 Vectors · Textract)
# ---------------------------------------------------------------------------

_ai_session: boto3.Session | None = None

def _get_ai_session() -> boto3.Session:
    """개인 계정 boto3 세션. AI_AWS_* 환경변수로 자격증명."""
    global _ai_session
    if _ai_session is None:
        access_key = os.environ.get("AI_AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AI_AWS_SECRET_ACCESS_KEY")
        session_token = os.environ.get("AI_AWS_SESSION_TOKEN")  # optional
        profile = os.environ.get("AI_AWS_PROFILE")

        if access_key and secret_key:
            _ai_session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=os.environ.get("AI_AWS_REGION", "us-east-1"),
            )
        elif profile:
            _ai_session = boto3.Session(
                profile_name=profile,
                region_name=os.environ.get("AI_AWS_REGION", "us-east-1"),
            )
        else:
            raise RuntimeError(
                "개인 계정 자격증명이 없습니다. "
                "AI_AWS_ACCESS_KEY_ID + AI_AWS_SECRET_ACCESS_KEY 또는 "
                "AI_AWS_PROFILE 환경변수를 설정하세요."
            )
    return _ai_session


_ai_region: str | None = None

def _ai_region_name() -> str:
    global _ai_region
    if _ai_region is None:
        _ai_region = os.environ.get("AI_AWS_REGION", "us-east-1")
    return _ai_region


# ---------------------------------------------------------------------------
# 공개 팩토리 함수 — AI 모듈용 (개인 계정)
# ---------------------------------------------------------------------------

def get_bedrock_runtime_client():
    """개인 계정 Bedrock Runtime 클라이언트."""
    return _get_ai_session().client("bedrock-runtime", region_name=_ai_region_name())


def get_s3vectors_client():
    """개인 계정 S3 Vectors 클라이언트."""
    return _get_ai_session().client("s3vectors", region_name=_ai_region_name())


def get_textract_client():
    """개인 계정 Textract 클라이언트."""
    return _get_ai_session().client("textract", region_name=_ai_region_name())


def get_s3_client_for_images():
    """개인 계정 S3 클라이언트 — 이미지 다운로드용 (크롤 결과 이미지가 개인 계정 S3에 있을 때)."""
    return _get_ai_session().client("s3", region_name=_ai_region_name())


# ---------------------------------------------------------------------------
# 공개 팩토리 함수 — BE 모듈용 (지원 계정, 인스턴스 프로파일)
# ---------------------------------------------------------------------------

_support_region: str | None = None

def _support_region_name() -> str:
    global _support_region
    if _support_region is None:
        _support_region = os.environ.get("AWS_REGION", "us-east-1")
    return _support_region


def get_dynamodb_resource():
    """지원 계정 DynamoDB resource (인스턴스 프로파일)."""
    return boto3.resource("dynamodb", region_name=_support_region_name())


def get_support_s3_client():
    """지원 계정 S3 클라이언트 (크롤 데이터 저장용)."""
    return boto3.client("s3", region_name=_support_region_name())


# ---------------------------------------------------------------------------
# 테스트 지원 — 세션 캐시 초기화
# ---------------------------------------------------------------------------

def _reset_cache() -> None:
    """단위 테스트에서 세션 캐시를 초기화할 때 사용. 프로덕션 코드에서 호출 금지."""
    global _ai_session, _ai_region, _support_region
    _ai_session = None
    _ai_region = None
    _support_region = None
```

- [ ] **Step 2: `ai/core/__init__.py` 에 export 추가**

현재 `ai/core/__init__.py` 내용을 확인하고 아래를 추가:

```python
from ai.core.aws_clients import (  # noqa: F401
    get_bedrock_runtime_client,
    get_s3vectors_client,
    get_textract_client,
    get_dynamodb_resource,
)
```

- [ ] **Step 3: 커밋**

```bash
git add ai/core/aws_clients.py ai/core/__init__.py
git commit -m "feat(ai): 계정별 boto3 세션 팩토리 추가 (개인/지원 계정 분리)"
```

---

## Task 2: AI 모듈 리전·모델·팩토리 교체 (4개 파일)

**Files:**
- Modify: `ai/core/bedrock_client.py`
- Modify: `ai/search/embed.py`
- Modify: `ai/search/vector_store.py`
- Modify: `ai/pipeline/vision.py`

- [ ] **Step 1: `ai/core/bedrock_client.py` 전체 교체**

```python
import json
import os

from ai.core.aws_clients import get_bedrock_runtime_client

_bedrock_client = None


def get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = get_bedrock_runtime_client()
    return _bedrock_client


def invoke_model(prompt: str, model_id: str | None = None) -> dict:
    """텍스트 프롬프트를 Bedrock Claude에 전송하고 응답 dict를 반환."""
    client = get_bedrock_client()
    model = model_id or os.getenv(
        "BEDROCK_LLM_MODEL_ID",
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = client.invoke_model(modelId=model, body=body)
    return json.loads(response["body"].read())


def invoke_model_with_image(prompt: str, image_b64: str, media_type: str = "image/jpeg") -> dict:
    """이미지 + 텍스트를 Bedrock Claude Vision에 전송."""
    client = get_bedrock_client()
    model = os.getenv(
        "BEDROCK_LLM_MODEL_ID",
        "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    })
    response = client.invoke_model(modelId=model, body=body)
    return json.loads(response["body"].read())
```

- [ ] **Step 2: `ai/search/embed.py` — `_get_embed_client` 수정**

`_get_embed_client` 함수만 아래로 교체 (나머지 로직 그대로):

```python
from ai.core.aws_clients import get_bedrock_runtime_client

_embed_client: "BedrockRuntimeClient | None" = None


def _get_embed_client() -> "BedrockRuntimeClient":
    global _embed_client
    if _embed_client is None:
        _embed_client = get_bedrock_runtime_client()
    return _embed_client
```

기존 `import boto3` 와 region_name 포함 코드 블록을 위 코드로 교체.

- [ ] **Step 3: `ai/search/vector_store.py` — `_get_s3vectors_client` 수정**

```python
from ai.core.aws_clients import get_s3vectors_client as _create_s3vectors_client

_s3vectors_client = None


def _get_s3vectors_client():
    global _s3vectors_client
    if _s3vectors_client is None:
        _s3vectors_client = _create_s3vectors_client()
    return _s3vectors_client
```

기존 `boto3.client("s3vectors", region_name=...)` 블록을 위 코드로 교체.

- [ ] **Step 4: `ai/pipeline/vision.py` — 세 곳의 boto3 직접 호출 수정**

`_download_s3_image` 함수 안의 `boto3.client("s3", ...)` 를 교체:

```python
from ai.core.aws_clients import get_s3_client_for_images, get_textract_client


def _download_s3_image(url: str) -> bytes:
    parsed = urlparse(url)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    s3 = get_s3_client_for_images()
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except Exception as exc:
        raise ImageNotFoundError(f"S3 이미지 접근 실패: {url} — {exc}") from exc
```

`_run_textract_ocr` 함수 안의 `boto3.client("textract", ...)` 를 교체:

```python
def _run_textract_ocr(image_bytes: bytes, url: str) -> None:
    try:
        textract = get_textract_client()
        response = textract.analyze_document(
            Document={"Bytes": image_bytes},
            FeatureTypes=["TABLES", "FORMS"],
        )
        blocks = response.get("Blocks", [])
        lines = [
            b["Text"]
            for b in blocks
            if b.get("BlockType") == "LINE" and b.get("Text")
        ]
        extracted = " | ".join(lines[:20])
        logger.info("Textract OCR (url=%s): %s", url, extracted if extracted else "(텍스트 없음)")
    except Exception as exc:
        logger.warning("Textract 호출 실패, 건너뜀 (url=%s): %s", url, exc)
```

파일 상단의 `_DEFAULT_AWS_REGION = "ap-northeast-2"` 및 기존 `import boto3` 를 제거하고 `from ai.core.aws_clients import get_s3_client_for_images, get_textract_client` 를 추가.

- [ ] **Step 5: 커밋**

```bash
git add ai/core/bedrock_client.py ai/search/embed.py ai/search/vector_store.py ai/pipeline/vision.py
git commit -m "refactor(ai): 개인 계정 boto3 팩토리 교체 및 리전/모델 기본값 us-east-1로 통일"
```

---

## Task 3: `ai/search/feedback.py` — DynamoDB 지원 계정 팩토리 교체 + 리전

**Files:**
- Modify: `ai/search/feedback.py`

DynamoDB는 지원 계정이므로 개인 계정 세션이 아닌 기본 자격증명(인스턴스 프로파일)을 쓴다.

- [ ] **Step 1: `_get_dynamodb` 함수 교체**

기존:
```python
def _get_dynamodb():
    return boto3.resource(
        "dynamodb",
        region_name=os.getenv("AWS_REGION", "ap-northeast-2"),
    )
```

교체:
```python
from ai.core.aws_clients import get_dynamodb_resource

def _get_dynamodb():
    return get_dynamodb_resource()
```

파일 상단의 `import boto3` 를 제거 (더 이상 직접 사용 안 함).

- [ ] **Step 2: 커밋**

```bash
git add ai/search/feedback.py
git commit -m "refactor(ai): feedback DynamoDB 클라이언트를 지원 계정 팩토리로 교체"
```

---

## Task 4: `shared/models.py` — `ChangeRecord` alias 추가

**Files:**
- Modify: `shared/models.py`

`dynamo_adapter.py` 와 `mock_adapters.py` 가 `ChangeRecord` 를 import 하는데, 모델에는 `ClassificationChange` 만 있어서 `ImportError` 가 발생한다. 가장 덜 침습적인 픽스는 alias 추가.

- [ ] **Step 1: `shared/models.py` 끝에 alias 추가**

```python
# ---------------------------------------------------------------------------
# 하위 호환 alias — dynamo_adapter 에서 ChangeRecord 로 참조 중
# ---------------------------------------------------------------------------

ChangeRecord = ClassificationChange
```

- [ ] **Step 2: 커밋**

```bash
git add shared/models.py
git commit -m "fix(shared): ChangeRecord alias 추가 (ClassificationChange 동일 모델)"
```

---

## Task 5: `be/adapters/dynamo_adapter.py` — 리전·sigungu denormalize

**Files:**
- Modify: `be/adapters/dynamo_adapter.py`

두 가지 수정:
1. 리전 기본값 `ap-northeast-2` → `us-east-1`
2. `save_hospital_meta` 에서 `sigungu`/`sido` top-level 속성을 DynamoDB 아이템에 추가 (GSI 사용을 위해)

- [ ] **Step 1: `__init__` 메서드 리전 수정**

```python
class DynamoAdapter:
    def __init__(self):
        self._resource = boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
```

- [ ] **Step 2: `save_hospital_meta` 에 sigungu/sido denormalize 추가**

```python
def save_hospital_meta(self, meta: HospitalMeta) -> None:
    item = meta.model_dump(mode="json")
    # GSI "sigungu-index" 를 위해 최상위 레벨로 복사 (DynamoDB 는 중첩 키 GSI 미지원)
    item["sigungu"] = meta.location.sigungu
    item["sido"] = meta.location.sido
    self._table("Hospitals").put_item(Item=item)
```

- [ ] **Step 3: `list_hospitals_by_sigungu` 확인** — 실제 DynamoDB GSI 쿼리를 써야 하므로 현재 코드는 맞다 (`Key("sigungu").eq(sigungu)`), 단 Step 2 가 없으면 GSI 가 작동 안 함.

- [ ] **Step 4: 커밋**

```bash
git add be/adapters/dynamo_adapter.py
git commit -m "fix(be): DynamoDB 리전 us-east-1, Hospitals GSI용 sigungu/sido denormalize"
```

---

## Task 6: `be/tests/harness/mock_adapters.py` — 버그 픽스

**Files:**
- Modify: `be/tests/harness/mock_adapters.py`

두 가지 버그 수정:
1. `ChangeRecord` → `ClassificationChange` (Task 4 에서 alias 추가했으므로 import 는 그대로 동작하나, 타입을 명시적으로 수정)
2. `list_hospitals_by_sigungu` 의 `h.sigungu` → `h.location.sigungu`

- [ ] **Step 1: `list_hospitals_by_sigungu` 픽스**

```python
def list_hospitals_by_sigungu(self, sigungu: str) -> list[HospitalMeta]:
    return [h for h in self._hospitals.values() if h.location.sigungu == sigungu]
```

- [ ] **Step 2: `ChangeRecord` import 를 `ClassificationChange` 로 변경** (alias 있어서 기능은 동일하지만 명시적으로 수정)

```python
from shared.models import (
    ClassificationChange,
    Classification,
    Confidence,
    CrawlData,
    FeedbackEntry,
    HospitalDescription,
    HospitalMeta,
    Location,
    PublicData,
    RelatedHospital,
    ServicesAndDoctors,
    SignalContributions,
)
```

`_changes: dict[str, list[ChangeRecord]]` → `_changes: dict[str, list[ClassificationChange]]`

`save_change_record(self, record: ChangeRecord)` → `save_change_record(self, record: ClassificationChange)`

`load_recent_changes(...) -> list[ChangeRecord]` → `load_recent_changes(...) -> list[ClassificationChange]`

- [ ] **Step 3: 커밋**

```bash
git add be/tests/harness/mock_adapters.py
git commit -m "fix(be): mock_adapters sigungu 접근 버그 수정, ChangeRecord → ClassificationChange"
```

---

## Task 7: `index_hospital` 시그니처 통합 — "1번 스키마 수정"

**Files:**
- Modify: `ai/search/vector_store.py`
- Modify: `ai/__init__.py`

**배경:** 현재 `ai/__init__.py` 에서 export 하는 `index_hospital(hospital_id, classification, description_text)` 는 위치 정보(`sido`, `sigungu`, `lat`, `lng`)를 S3 Vectors 메타데이터에 기록하지 않는다. 그 결과 S3 Vectors 에는 위치 데이터가 없어서 위치 기반 검색 전체가 작동하지 않는다. `index_hospital_with_meta` 가 올바른 함수지만 export 되어 있지 않다.

수정: 두 함수를 통합하여 `index_hospital` 이 위치 파라미터를 필수로 받도록 시그니처를 변경한다.

- [ ] **Step 1: `ai/search/vector_store.py` 에서 `index_hospital` 교체**

기존 `index_hospital` 함수를 `index_hospital_with_meta` 로직으로 교체. `index_hospital_with_meta` 는 제거.

```python
def index_hospital(
    hospital_id: str,
    classification: Classification,
    description_text: str,
    sido: str,
    sigungu: str,
    lat: float | None = None,
    lng: float | None = None,
) -> None:
    """병원 분류 결과를 위치 정보 포함해 S3 Vectors에 적재한다.

    Args:
        hospital_id: 병원 고유 ID
        classification: AI 분류 결과
        description_text: 임베딩 대상 텍스트 (generate_description 단락 합본 권장)
        sido: 시도 (예: "서울특별시")
        sigungu: 시군구 (예: "성북구")
        lat: 위도 (없으면 None — 위치 기반 검색에서 제외됨)
        lng: 경도
    """
    bucket = os.getenv("S3_VECTOR_BUCKET")
    index_name = os.getenv("S3_VECTOR_INDEX", "hospital-index")
    if not bucket:
        raise S3VectorsError("환경변수 S3_VECTOR_BUCKET 이 설정되지 않았습니다.")

    vector = embed_text(description_text)
    metadata: dict = {
        "standard_specialty": classification.standard_specialty,
        "primary_focus": json.dumps(classification.primary_focus, ensure_ascii=False),
        "confidence_score": classification.confidence.score,
        "sido": sido,
        "sigungu": sigungu,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    if lat is not None:
        metadata["lat"] = lat
    if lng is not None:
        metadata["lng"] = lng

    client = _get_s3vectors_client()
    try:
        client.put_vectors(
            vectorBucketName=bucket,
            indexName=index_name,
            vectors=[{"key": hospital_id, "data": {"float32": vector}, "metadata": metadata}],
        )
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error("S3 Vectors PutVectors 실패 (hospital_id=%s): %s", hospital_id, error_code)
        raise S3VectorsError(f"PutVectors 실패 (hospital_id={hospital_id}): {error_code}") from exc
    except Exception as exc:
        logger.error("S3 Vectors PutVectors 실패 (hospital_id=%s): %s", hospital_id, exc)
        raise S3VectorsError(f"PutVectors 실패 (hospital_id={hospital_id}): {exc}") from exc

    logger.info(
        "index_hospital 완료: hospital_id=%s (%s %s), index=%s/%s",
        hospital_id, sido, sigungu, bucket, index_name,
    )
```

기존 `index_hospital_with_meta` 함수 전체 삭제.

- [ ] **Step 2: `be/handlers/index_hospital.py` 의 `index_hospital` 호출 업데이트**

```python
# 7. S3 Vectors 인덱싱
embedding_text = "\n".join(p.text for p in description.paragraphs)
index_hospital(
    hospital_id=hospital_id,
    classification=classification,
    description_text=embedding_text,
    sido=hospital_meta.location.sido,
    sigungu=hospital_meta.location.sigungu,
    lat=hospital_meta.location.lat,
    lng=hospital_meta.location.lng,
)
```

- [ ] **Step 3: 커밋**

```bash
git add ai/search/vector_store.py be/handlers/index_hospital.py
git commit -m "feat(ai): index_hospital 위치 파라미터 통합 — S3 Vectors에 lat/lng 기록"
```

---

## Task 8: `be/handlers/api.py` Mangum 제거 + `be/main.py` 추가

**Files:**
- Modify: `be/handlers/api.py`
- Create: `be/main.py`

- [ ] **Step 1: `be/handlers/api.py` 수정**

파일 맨 위 docstring 변경:
```python
"""FastAPI 앱 — EC2 uvicorn 으로 실행."""
```

삭제:
```python
from mangum import Mangum
```

삭제 (파일 맨 아래):
```python
# Lambda 핸들러 (Mangum 어댑터)
handler = Mangum(app, lifespan="off")
```

`CORS allow_origins` 수정 — PoC에서는 `["*"]` 유지해도 무방.

최종 파일은:
```python
"""FastAPI 앱 — EC2 uvicorn 으로 실행."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from be.api.feedback import router as feedback_router
from be.api.history import router as history_router
from be.api.hospital import router as hospital_router
from be.api.search import router as search_router

app = FastAPI(
    title="ClinicFocus API",
    description="병원 실제 주력 분야 검색 서비스",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(hospital_router)
app.include_router(history_router)
app.include_router(feedback_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

- [ ] **Step 2: `be/main.py` 신규 생성**

```python
"""EC2 uvicorn 진입점.

실행:
    python -m uvicorn be.main:app --host 0.0.0.0 --port 8000 --workers 1

또는:
    python be/main.py
"""
import uvicorn

from be.handlers.api import app  # noqa: F401

if __name__ == "__main__":
    import os
    uvicorn.run(
        "be.handlers.api:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        workers=1,
        reload=False,
    )
```

- [ ] **Step 3: Lambda 핸들러 서명 → EC2 함수 전환**

`be/handlers/index_hospital.py` 의 `handler(event, context)` → `run_index_pipeline(hospital_id: str)` 로 변경:

```python
"""병원 인덱싱 파이프라인 — AI 분류 + 설명 생성 + DB 적재 + 벡터 인덱싱."""

from __future__ import annotations

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter
from shared.models import CrawlData, HospitalMeta

from ai import (
    classify_hospital,
    extract_services_and_doctors,
    find_related_hospitals,
    generate_description,
    index_hospital,
)


def run_index_pipeline(hospital_id: str) -> dict:
    """
    S3에서 CrawlData 로드 → AI 분류 → 설명 생성 → DynamoDB 적재 → 벡터 인덱싱.
    EC2 스크립트나 큐 컨슈머에서 직접 호출.
    """
    db = DynamoAdapter()
    s3 = S3Adapter()

    crawl_data = s3.load_crawl_data(hospital_id)
    if not crawl_data:
        return {"status": "error", "reason": "crawl_data_not_found", "hospital_id": hospital_id}

    hospital_meta = db.load_hospital_meta(hospital_id)
    if not hospital_meta:
        return {"status": "error", "reason": "hospital_meta_not_found", "hospital_id": hospital_id}

    classification = classify_hospital(crawl_data)

    services_and_doctors = extract_services_and_doctors(
        crawl_data=crawl_data,
        classification=classification,
        vision_results=[],
    )

    description = generate_description(
        classification=classification,
        detailed_signals=classification.detailed_signals,
        hospital_meta=hospital_meta,
    )

    related = find_related_hospitals(
        hospital_id=hospital_id,
        location=hospital_meta.location,
        primary_focus=classification.primary_focus,
        excluded_services=services_and_doctors.excluded_services,
    )

    db.save_classification(classification)
    db.save_description(description)
    db.save_services_and_doctors(hospital_id, services_and_doctors)
    db.save_related_hospitals(hospital_id, related)

    embedding_text = "\n".join(p.text for p in description.paragraphs)
    index_hospital(
        hospital_id=hospital_id,
        classification=classification,
        description_text=embedding_text,
        sido=hospital_meta.location.sido,
        sigungu=hospital_meta.location.sigungu,
        lat=hospital_meta.location.lat,
        lng=hospital_meta.location.lng,
    )

    return {"status": "indexed", "hospital_id": hospital_id}
```

`be/handlers/crawl_trigger.py` 의 `handler(event, context)` → `run_crawl_trigger(sido_code: str | None = None, sigungu_code: str | None = None)` 로 변경. 기존 함수 바디는 그대로, 서명과 SQS 이벤트 파싱만 제거.

`be/handlers/crawl_hospital.py` 의 `handler(event, context)` → `run_crawl(hospital_id: str, website_url: str)` 로 변경. SQS 레코드 파싱 제거.

- [ ] **Step 4: 커밋**

```bash
git add be/handlers/api.py be/main.py be/handlers/index_hospital.py be/handlers/crawl_trigger.py be/handlers/crawl_hospital.py
git commit -m "refactor(be): Mangum 제거, uvicorn 진입점 추가, 핸들러 Lambda 서명 → EC2 함수 전환"
```

---

## Task 9: `requirements.txt` mangum 제거, `template.yaml` 삭제

**Files:**
- Modify: `requirements.txt`
- Delete: `template.yaml`

- [ ] **Step 1: `requirements.txt` 에서 `mangum>=0.17.0` 줄 삭제**

최종 내용:
```
# shared + be 의존성
pydantic>=2.0
fastapi>=0.100.0
httpx>=0.25.0
beautifulsoup4>=4.12.0
boto3>=1.34.0
uvicorn>=0.24.0

# 테스트
pytest>=7.0
pytest-asyncio>=0.21.0
```

- [ ] **Step 2: `template.yaml` 삭제**

```bash
git rm template.yaml
```

- [ ] **Step 3: 커밋**

```bash
git add requirements.txt
git commit -m "chore(be): mangum 의존성 제거, template.yaml 삭제 (SAM 미사용)"
```

---

## Task 10: `.env.example` 작성

**Files:**
- Create: `.env.example`

EC2 에서 실행할 때 필요한 환경변수 전체 목록. 이 파일을 보고 EC2 에 `.env` 를 만들면 됨.

- [ ] **Step 1: `.env.example` 작성**

```bash
# ── 지원 계정 (EC2 인스턴스 프로파일로 자동 인증, 별도 키 불필요) ──────────────
AWS_REGION=us-east-1

# ── 개인 계정 (Bedrock · S3 Vectors · Textract) ───────────────────────────
# 방법 A: 액세스 키 직접 입력 (EC2에서 권장)
AI_AWS_ACCESS_KEY_ID=AKIA...
AI_AWS_SECRET_ACCESS_KEY=...
AI_AWS_SESSION_TOKEN=          # 임시 자격증명(STS) 쓸 때만

# 방법 B: 프로파일 이름 (~/.aws/credentials 에 설정된 경우)
# AI_AWS_PROFILE=personal

AI_AWS_REGION=us-east-1

# ── Bedrock 모델 ──────────────────────────────────────────────────────────
BEDROCK_LLM_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0

# ── S3 Vectors (개인 계정) ────────────────────────────────────────────────
S3_VECTOR_BUCKET=<username>-hospital-vectors
S3_VECTOR_INDEX=hospital-index

# ── DynamoDB (지원 계정, 인스턴스 프로파일로 인증) ──────────────────────────
# 테이블 이름 앞에 접두사를 붙이고 싶을 때 (예: dev_, staging_)
TABLE_PREFIX=

# ── 크롤러 ────────────────────────────────────────────────────────────────
# 크롤링 결과 저장용 S3 버킷 (지원 계정)
CRAWL_S3_BUCKET=<username>-clinic-crawl

# ── API 서버 ──────────────────────────────────────────────────────────────
PORT=8000

# ── AI 비용 제어 ──────────────────────────────────────────────────────────
MAX_VISION_IMAGES=10
CONFIDENCE_THRESHOLD_HIGH=95
CONFIDENCE_THRESHOLD_LOW=70
```

- [ ] **Step 2: 커밋**

```bash
git add .env.example
git commit -m "docs: .env.example 추가 — EC2 환경변수 전체 목록"
```

---

## Task 11: AWS 인프라 세팅 스크립트

**Files:**
- Create: `be/scripts/setup_dynamodb.py`
- Create: `ai/scripts/setup_vectors.py`

이 스크립트들은 EC2에서 한 번만 실행한다.

- [ ] **Step 1: `be/scripts/setup_dynamodb.py` 작성**

```python
"""
DynamoDB 테이블 생성 스크립트 (지원 계정, 인스턴스 프로파일 사용).

실행:
    python be/scripts/setup_dynamodb.py

이미 테이블이 있으면 ResourceInUseException 이 발생하고 무시된다.
"""
import os
import boto3
from botocore.exceptions import ClientError

REGION = os.environ.get("AWS_REGION", "us-east-1")
PREFIX = os.environ.get("TABLE_PREFIX", "")


def tbl(name: str) -> str:
    return f"{PREFIX}{name}"


def create_table_if_not_exists(ddb, **kwargs):
    try:
        table = ddb.create_table(**kwargs)
        table.wait_until_exists()
        print(f"  생성됨: {kwargs['TableName']}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            print(f"  이미 존재: {kwargs['TableName']}")
        else:
            raise


def main():
    ddb = boto3.resource("dynamodb", region_name=REGION)

    print("DynamoDB 테이블 생성 시작...")

    # Hospitals — PK: hospital_id, GSI: sigungu-index(sigungu)
    create_table_if_not_exists(
        ddb,
        TableName=tbl("Hospitals"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "hospital_id", "AttributeType": "S"},
            {"AttributeName": "sigungu", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "sigungu-index",
            "KeySchema": [{"AttributeName": "sigungu", "KeyType": "HASH"}],
            "Projection": {"ProjectionType": "ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )

    # Classifications — PK: hospital_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("Classifications"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hospital_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # HospitalDescriptions — PK: hospital_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("HospitalDescriptions"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hospital_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # ServicesAndDoctors — PK: hospital_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("ServicesAndDoctors"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hospital_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # RelatedHospitals — PK: hospital_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("RelatedHospitals"),
        KeySchema=[{"AttributeName": "hospital_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "hospital_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )

    # Feedback — PK: hospital_id, SK: feedback_id
    create_table_if_not_exists(
        ddb,
        TableName=tbl("Feedback"),
        KeySchema=[
            {"AttributeName": "hospital_id", "KeyType": "HASH"},
            {"AttributeName": "feedback_id", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "hospital_id", "AttributeType": "S"},
            {"AttributeName": "feedback_id", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # ChangeHistory — PK: hospital_id, SK: changed_at
    create_table_if_not_exists(
        ddb,
        TableName=tbl("ChangeHistory"),
        KeySchema=[
            {"AttributeName": "hospital_id", "KeyType": "HASH"},
            {"AttributeName": "changed_at", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "hospital_id", "AttributeType": "S"},
            {"AttributeName": "changed_at", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    print("DynamoDB 테이블 생성 완료.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: `ai/scripts/setup_vectors.py` 작성**

```python
"""
S3 Vectors 버킷 + 인덱스 생성 스크립트 (개인 계정, AI_AWS_* 환경변수 사용).

실행:
    python ai/scripts/setup_vectors.py

이미 존재하면 에러 없이 skip 된다.
"""
import os
import sys

# 환경변수 설정 확인
def _check_env():
    has_keys = os.environ.get("AI_AWS_ACCESS_KEY_ID") and os.environ.get("AI_AWS_SECRET_ACCESS_KEY")
    has_profile = os.environ.get("AI_AWS_PROFILE")
    bucket = os.environ.get("S3_VECTOR_BUCKET")
    if not (has_keys or has_profile):
        print("오류: AI_AWS_ACCESS_KEY_ID + AI_AWS_SECRET_ACCESS_KEY 또는 AI_AWS_PROFILE 을 설정하세요.")
        sys.exit(1)
    if not bucket:
        print("오류: S3_VECTOR_BUCKET 환경변수를 설정하세요. (예: username-hospital-vectors)")
        sys.exit(1)
    return bucket


def main():
    bucket_name = _check_env()
    index_name = os.environ.get("S3_VECTOR_INDEX", "hospital-index")

    # ai/core/aws_clients 팩토리 사용
    from ai.core.aws_clients import get_s3vectors_client
    client = get_s3vectors_client()

    # 1. 버킷 생성
    try:
        client.create_vector_bucket(vectorBucketName=bucket_name)
        print(f"  버킷 생성됨: {bucket_name}")
    except Exception as e:
        if "already exists" in str(e).lower() or "BucketAlreadyExists" in str(type(e).__name__):
            print(f"  버킷 이미 존재: {bucket_name}")
        else:
            print(f"  버킷 생성 실패: {e}")
            raise

    # 2. 인덱스 생성 (차원 1024 = Titan Embed Text v2)
    try:
        client.create_index(
            vectorBucketName=bucket_name,
            indexName=index_name,
            dataType="float32",
            dimension=1024,
            distanceMetric="cosine",
        )
        print(f"  인덱스 생성됨: {index_name} (bucket={bucket_name}, dim=1024, cosine)")
    except Exception as e:
        if "already exists" in str(e).lower() or "IndexAlreadyExists" in str(type(e).__name__):
            print(f"  인덱스 이미 존재: {index_name}")
        else:
            print(f"  인덱스 생성 실패: {e}")
            raise

    print("S3 Vectors 설정 완료.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 커밋**

```bash
git add be/scripts/setup_dynamodb.py ai/scripts/setup_vectors.py
git commit -m "chore: DynamoDB·S3 Vectors 인프라 초기화 스크립트 추가"
```

---

## Task 12: BE 개발자(김경재)용 GitHub 이슈 작성

이 task 는 코드 작성이 아니라 `gh` CLI 로 GitHub 이슈를 생성한다.

- [ ] **Step 1: 이슈 #1 — Mangum 제거 후 핸들러 함수 호출 방식 변경**

```bash
gh issue create \
  --title "[BE] Lambda 핸들러 → EC2 함수 전환: index_hospital·crawl 파이프라인 호출 방식 변경" \
  --body "$(cat <<'EOF'
## 배경

Lambda + SQS → EC2 단일 프로세스로 전환함에 따라 Mangum 과 Lambda 핸들러 서명이 제거됐습니다.

## 변경 내용 (이미 머지됨)

| 파일 | 변경 전 | 변경 후 |
|------|---------|---------|
| `be/handlers/api.py` | `handler = Mangum(app)` | Mangum 제거, `app` 만 남음 |
| `be/handlers/index_hospital.py` | `handler(event, context)` | `run_index_pipeline(hospital_id: str)` |
| `be/handlers/crawl_trigger.py` | `handler(event, context)` | `run_crawl_trigger(sido_code, sigungu_code)` |
| `be/handlers/crawl_hospital.py` | `handler(event, context)` | `run_crawl(hospital_id, website_url)` |
| `be/main.py` | 없음 | uvicorn 진입점 추가 |

## 실행 방법

```bash
# API 서버 시작
python be/main.py
# 또는
python -m uvicorn be.handlers.api:app --host 0.0.0.0 --port 8000

# 인덱싱 파이프라인 수동 실행 (Python REPL 또는 스크립트에서)
from be.handlers.index_hospital import run_index_pipeline
run_index_pipeline("hospital_id_here")
```

## 해야 할 일 (김경재)

- [ ] EC2에서 `python be/main.py` 로 실행 되는지 확인
- [ ] 크롤러 실행 스크립트(`be/scripts/`)가 새 함수 서명으로 `run_crawl_trigger`, `run_crawl` 을 호출하도록 업데이트
- [ ] SQS 큐가 남아있다면 큐 컨슈머 루프를 별도 스크립트로 작성 (Lambda 트리거 대신)
EOF
)"
```

- [ ] **Step 2: 이슈 #2 — DynamoDB 테이블 생성**

```bash
gh issue create \
  --title "[BE] DynamoDB 테이블 생성 (지원 계정, us-east-1)" \
  --body "$(cat <<'EOF'
## 해야 할 일

EC2 인스턴스 프로파일이 설정된 환경에서 아래 스크립트를 한 번 실행:

```bash
# EC2 에서
cd /path/to/clinic-focus
AWS_REGION=us-east-1 python be/scripts/setup_dynamodb.py
```

## 생성되는 테이블 (7개)

| 테이블 | PK | SK | GSI |
|--------|----|----|-----|
| Hospitals | hospital_id | — | sigungu-index(sigungu) |
| Classifications | hospital_id | — | — |
| HospitalDescriptions | hospital_id | — | — |
| ServicesAndDoctors | hospital_id | — | — |
| RelatedHospitals | hospital_id | — | — |
| Feedback | hospital_id | feedback_id | — |
| ChangeHistory | hospital_id | changed_at | — |

## 주의사항

- 리전: `us-east-1` (지원 계정)
- BillingMode: `PAY_PER_REQUEST` (PoC에 적합)
- `TABLE_PREFIX` 환경변수로 테이블 이름 앞에 접두사 가능 (예: `dev_`)
EOF
)"
```

- [ ] **Step 3: 이슈 #3 — `index_hospital` 시그니처 변경 공지**

```bash
gh issue create \
  --title "[BE] index_hospital 시그니처 변경 — sido·sigungu·lat·lng 파라미터 추가 (필수)" \
  --body "$(cat <<'EOF'
## 변경 내용

`index_hospital` 함수가 위치 정보를 필수로 받도록 시그니처가 바뀌었습니다.

**변경 전:**
```python
index_hospital(hospital_id, classification, description_text)
```

**변경 후:**
```python
index_hospital(
    hospital_id,
    classification,
    description_text,
    sido,         # 필수
    sigungu,      # 필수
    lat=None,     # 선택 (없으면 위치 검색 결과에서 제외)
    lng=None,     # 선택
)
```

## 영향 받는 파일

`be/handlers/index_hospital.py` 는 이미 업데이트 됨. 만약 다른 곳에서 `index_hospital` 을 직접 호출하고 있다면 동일하게 수정 필요.

## 이유

위치 파라미터를 넣지 않으면 S3 Vectors 메타데이터에 lat/lng 가 없어서 위치 기반 검색이 전혀 작동하지 않습니다.
EOF
)"
```

---

## Task 13: 하네스 테스트 — 변경사항 smoke test

**Files:**
- Modify: `ai/scripts/smoke_test.py`

아직 실제 AWS 없이 실행 가능한 부분만 테스트.

- [ ] **Step 1: `smoke_test.py` 에 환경변수 체크 추가**

`ai/scripts/smoke_test.py` 를 열어서, 실제 Bedrock 호출 전에 `AI_AWS_ACCESS_KEY_ID` 설정 여부를 확인하는 가드 추가:

```python
import os
import sys

def _check_aws_config():
    has_keys = os.environ.get("AI_AWS_ACCESS_KEY_ID") and os.environ.get("AI_AWS_SECRET_ACCESS_KEY")
    has_profile = os.environ.get("AI_AWS_PROFILE")
    if not (has_keys or has_profile):
        print("[SKIP] AI_AWS_ACCESS_KEY_ID 또는 AI_AWS_PROFILE 미설정 → AWS 호출 테스트 건너뜀")
        return False
    return True
```

- [ ] **Step 2: `mock_adapters.py` import 오류 없는지 확인**

```bash
cd d:\Develop\GitHub\clinic-focus
python -c "from be.tests.harness.mock_adapters import MockDynamoAdapter; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: `shared.models` import 오류 없는지 확인**

```bash
python -c "from shared.models import ChangeRecord, ClassificationChange; print(ChangeRecord is ClassificationChange)"
```

Expected: `True`

- [ ] **Step 4: `be/handlers/api.py` import 오류 없는지 확인 (Mangum 없이)**

```bash
python -c "from be.handlers.api import app; print('FastAPI app:', app.title)"
```

Expected: `FastAPI app: ClinicFocus API`

- [ ] **Step 5: 커밋**

```bash
git add ai/scripts/smoke_test.py
git commit -m "test(ai): smoke_test AWS 환경변수 가드 추가"
```

---

## 실행 순서 요약

```
Task 1  → aws_clients.py 팩토리 신규
Task 2  → bedrock, embed, vector_store, vision 팩토리 교체
Task 3  → feedback DynamoDB 팩토리 교체
Task 4  → shared/models.py ChangeRecord alias
Task 5  → dynamo_adapter 리전·sigungu 픽스
Task 6  → mock_adapters 버그 픽스
Task 7  → index_hospital 시그니처 통합 (★ 1번 스키마)
Task 8  → Mangum 제거 + uvicorn 진입점
Task 9  → requirements.txt + template.yaml
Task 10 → .env.example
Task 11 → setup_dynamodb.py + setup_vectors.py
Task 12 → GitHub 이슈 3개 생성
Task 13 → smoke test 및 import 검증
```

## 검증 체크리스트

- [ ] `python -c "from ai.core.aws_clients import get_bedrock_runtime_client"` 오류 없음
- [ ] `python -c "from be.handlers.api import app"` 오류 없음 (Mangum import 없이)
- [ ] `python -c "from shared.models import ChangeRecord"` 오류 없음
- [ ] `python -c "from be.tests.harness.mock_adapters import MockDynamoAdapter"` 오류 없음
- [ ] `requirements.txt` 에 `mangum` 없음
- [ ] `template.yaml` 없음
- [ ] `.env.example` 존재
- [ ] `be/main.py` 존재
