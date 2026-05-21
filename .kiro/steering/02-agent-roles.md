---
inclusion: always
---

# 트랙별 역할 및 에이전트 구조

> 원본: `.claude/agents/*.md`, 루트 `CLAUDE.md`

## 트랙 리더

| 에이전트 | 트랙 | 담당 범위 |
|---|---|---|
| `fe-engineer` | `fe/` | React + Vite + TS + Tailwind + shadcn/ui + TanStack Query + 카카오맵 SDK. 검색 결과·병원 상세 페이지(9개 영역)·지도 검색·익명 피드백 UI |
| `be-engineer` | `be/` + `shared/` | FastAPI + uvicorn + Pydantic + boto3 + httpx + BS4. API 엔드포인트, 크롤러, 심평원 공공 API, DynamoDB 스키마, CORS |
| `ai-engineer` | `ai/` + `shared/` | Bedrock + S3 Vectors + Textract. 분류·생성·검색·Vision·시그널 융합·임베딩·인덱싱 |

## ai/ 서브에이전트 (ai-engineer 위임)

| 에이전트 | 역할 |
|---|---|
| `prompt-engineer` | `generate_description` 프롬프트 설계·튜닝, 의료법 5규칙 강제, `ai/prompts/*.md` 관리 |
| `vector-search-engineer` | S3 Vectors, `search_similar`, `index_hospital`, `embed_text`, 메타필터 |
| `vision-analyst` | Bedrock Vision + Textract, `analyze_images`, 시술·기기 사진 분류, `MAX_VISION_IMAGES` 비용 관리 |
| `signal-fusion-engineer` | 4 시그널 교차 검증, `classify_hospital`, 자칭 도배 페널티, `recompute_confidence` |

## 핵심 함수 책임

| 함수 | 담당 | 설명 |
|---|---|---|
| `classify_hospital` | ai-engineer | 4 시그널 교차 검증 → Classification 반환 |
| `generate_description` | prompt-engineer | 자연어 통합 설명 생성 ⭐ 본 서비스 핵심 |
| `extract_services_and_doctors` | ai-engineer | 진료 항목·기기·의료진 추출 |
| `index_hospital` | vector-search-engineer | S3 Vectors 임베딩 적재 (sido/sigungu/lat/lng 포함) |
| `search_similar` | vector-search-engineer | 자연어 + 위치 복합 검색 |
| `recompute_confidence` | signal-fusion-engineer | 피드백 누적 시 신뢰도 재계산 |
| `find_related_hospitals` | ai-engineer | 관련 병원 추천 (same_focus + fills_gap) |
| `aggregate_feedback_stats` | be-engineer | 피드백 통계 집계 (DynamoDB) |

## 작업 위임 흐름 (ai/ 트랙)

```
사용자 요청 (ai/ 관련)
  ↓
ai-engineer (직접 처리 / 위임 판단)
  ↓
prompt-engineer · vector-search-engineer · vision-analyst · signal-fusion-engineer
  (병렬 가능 시 동시 호출)
  ↓
medical-language-reviewer (의료법) · python-reviewer (코드)
  ↓
ai-engineer 통합
```

## shared/models.py 변경 시

BE·AI 양쪽 모두 영향. 한쪽에서 바꾸면 반드시 다른 쪽에 통보하고 동시 업데이트.
