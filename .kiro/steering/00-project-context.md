---
inclusion: always
---

# clinic-focus 프로젝트 컨텍스트

> 원본 상세 문서: `docs/overview.md`, `docs/dev-roadmap.md`

## 한 줄 정의

**표준 진료과목 카테고리 너머, 병원이 실제로 무엇에 집중하는지를 알려주는 검색 서비스.**

## 팀 구성

| 담당 | 영역 |
|---|---|
| 최비성 | AI / RAG / 분류 알고리즘 (`ai/`) |
| 하재원 | 프론트엔드 (`fe/`) |
| 김경재 | 백엔드 / 데이터 수집 (`be/`) |

## 모노레포 구조

```
clinic-focus/
├── fe/         React + Vite + TS + Tailwind + shadcn/ui + TanStack Query + 카카오맵 SDK
├── be/         FastAPI + uvicorn + Pydantic + boto3 + httpx + BS4 (EC2 운영)
├── ai/         Bedrock (Haiku/Nova 지원·Sonnet 4.5 Vision 개인) + Titan Embed v2 + Bedrock Knowledge Base (강사 제공 `kmuproj-team-03`)
├── shared/     공유 Pydantic 모델 (BE·AI 양쪽 import, FE는 OpenAPI→TS 자동 생성)
└── docs/       4대 문서 (overview, dev-roadmap, API-FE-BE, API-BE-AI)
```

## BE ↔ AI 호출 방식

같은 EC2 인스턴스 단일 Python 프로세스. BE는 AI 함수를 Python import로 직접 호출 (HTTP 아님).

```python
from ai import classify_hospital, generate_description
from shared.models import CrawlData
```

## AWS 계정 구조

| 계정 | 서비스 | 자격증명 |
|---|---|---|
| **지원 계정** | EC2, DynamoDB, S3, API Gateway, Bedrock(Haiku/Nova/Titan), **Bedrock Knowledge Base (`kmuproj-team-03`)** | EC2 인스턴스 프로파일 (액세스 키 발급 불가) |
| **개인 계정** | Bedrock (Sonnet 4.5 — Vision 시연 한정) | `AI_AWS_PROFILE=personal` 또는 `AI_AWS_ACCESS_KEY_ID` |

## 핵심 모델 ID

- LLM (지원, 트랙 B 시연): `anthropic.claude-haiku-4-5-...` 또는 `amazon.nova-...`
- Vision (개인, 트랙 C 시연): `anthropic.claude-sonnet-4-5-20250929-v1:0`
- Embedding (지원): `amazon.titan-embed-text-v2:0` (차원 1024) — KB가 자체 사용
- Knowledge Base ID (지원): `GTBJ6HLFDK` (`kmuproj-team-03`)

## PoC 범위 — 포함하지 않는 것

Docker / CI·CD / 로드밸런싱 / 인증·로그인 / SEO·SSR / 다크모드 / B2B SDK / 자동 갱신 파이프라인 / Elasticsearch·Airflow·Redis 같은 자체 호스팅 오픈소스 인프라
