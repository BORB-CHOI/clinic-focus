# ai/ — AI · RAG 트랙 (최비성)

상위 컨텍스트는 `../CLAUDE.md`, 함수 명세는 `../docs/API-BE-AI.md`.

## 스택

| 항목 | 선택 |
|---|---|
| 언어 | Python 3.11+ (BE와 동일 EC2 프로세스) |
| LLM/Vision (시연 10개) — 지원 계정 | Bedrock Haiku 4.5 또는 Nova (강사 제공 자원, 모델·범위 제한) |
| Vision 고품질 시연 (10개) — 개인 계정 | Bedrock Claude Sonnet 4.5 (`anthropic.claude-sonnet-4-5-20250929-v1:0`) |
| OCR | Bedrock Vision으로 흡수 (한국어 미지원으로 Textract 제거) |
| Embedding | Bedrock Titan Embed Text v2 (`amazon.titan-embed-text-v2:0`, 1024 dim, 지원 계정) |
| Vector store | S3 Vectors (`s3vectors:PutVectors` / `QueryVectors`, 지원 계정) — 강사 제공 버킷 `bedrock-knowledge-base-1tvot3` |
| 전체 1만 병원 텍스트 분류 | **룰 기반** (LLM 미사용, 키워드/빈도) |
| RAG 프레임워크 | **직접 구현** (LangChain 안 씀 — 4 시그널 교차 검증 로직 통제 위해) |
| 데이터 모델 | Pydantic — `../shared/models.py` 단일 소스 |

> S3 Vectors · Titan Embed · Haiku/Nova 는 **지원 계정**(us-east-1) 자원으로 EC2 인스턴스
> 프로파일로 자동 인증. Sonnet 4.5(Vision 시연용)만 **개인 계정** 자격증명으로 boto3
> 클라이언트를 따로 생성한다. 자세한 건 `../CLAUDE.md`의 "AWS 계정·인프라 구조" 참조.

## AI 트랙 3트랙 구조

지원 계정 Bedrock은 **Haiku/Nova + 10개 병원 한도**로 제공받음. 전체 1만 병원에 LLM을 못 돌리므로 분류는 룰 기반으로 베이스라인을 깔고, LLM/Vision은 시연 10개에 집중.

| 트랙 | 대상 | 모델 | 계정 | 범위 |
|---|---|---|---|---|
| **A. 룰 기반 분류** | 자칭 컨셉 추출 (LLM 미사용) | 키워드/빈도 룰 | — | 서울 5개구 1만 |
| **B. LLM 텍스트 시연** | 자칭 추출 + `generate_description` | Haiku 4.5 / Nova | 지원 | 10개 |
| **C. Vision 시연** | 이미지 분석 (OCR + 시각) | Sonnet 4.5 | 개인 | 10개 |

- A는 1만 풀커버 베이스라인. 비용 0, 전국 7만 확장에도 비용 0.
- B·C는 **같은 10개 병원**에 적용해 룰 결과와 비교 시연. 차별 효과를 자기 눈으로 보여주는 데모 핵심.
- 신뢰도 점수가 트랙별로 자연스럽게 차등화됨: A만 → 50~70% "추정/정보 부족" / B·C 결합 → 80~95% "확실".
- 정제(HTML 잡음 제거)는 **BE 책임** — `be/core/crawler.py`의 페이지 간 중복 단락 제거 + 의료 사이트 공통 잡음 블랙리스트 (modoo 안내, 개인정보취급방침, 환자권리장전, 이용약관, 404 등).

## 모듈 export

`ai/__init__.py`가 BE에 노출하는 함수 (`../docs/API-BE-AI.md` 명세):

- `classify_hospital(crawl_data, use_vision=True) -> Classification`
- `generate_description(classification, detailed_signals, hospital_meta) -> HospitalDescription` ⭐ **핵심**
- `extract_services_and_doctors(crawl_data, classification, vision_results) -> ServicesAndDoctors`
- `find_related_hospitals(hospital_id, location, primary_focus, excluded_services, limit=5) -> list[RelatedHospital]`
- `aggregate_feedback_stats(hospital_id) -> FeedbackStats`
- `search_similar(query: SearchQuery) -> list[SearchResult]`
- `index_hospital(hospital_id, classification, description_text) -> None`
- `recompute_confidence(hospital_id, recent_feedback) -> Confidence`
- `embed_text(text) -> list[float]`
- `analyze_images(image_urls, extract_text=False) -> list[ImageAnalysisResult]`

## `generate_description` 프롬프트 원칙 ⭐ 절대 어기지 말 것

이 함수의 출력이 본 서비스의 진짜 차별점이고 의료법 회색지대를 회피하는 자리다. 프롬프트에서 다음을 강제:

1. **주체 명시 표현 의무** — "이 병원이 자기 사이트에서 ~를 메인으로 표시함" 형태만 허용. "이 병원은 ~를 잘 본다" 금지
2. **출처 시그널 태그 의무** — 각 단락의 `citations` 리스트가 비어선 안 됨. `["self_claim", "vision", "blog", "reviews", "public_data"]` 중에서
3. **평가·추천 표현 금지** — "잘 본다" "추천한다" "전문" 같은 의료광고 회색지대 형용사 사용 금지
4. **약점·주의사항 포함** — 보유하지 않은 장비, 다루지 않는 분야 명시. 헛걸음 방지의 핵심
5. **출력은 구조화된 JSON** — `HospitalDescription` Pydantic 모델로 파싱. 검증 실패 시 재시도 또는 `DescriptionValidationError`

프롬프트 템플릿은 `ai/prompts/hospital_description.md`에 분리. 표준 진료과목별로 따로 관리 (피부과·정형외과·이비인후과·안과 등).

## 4 시그널 교차 검증

| 시그널 | 소스 | 가중치 |
|---|---|---|
| 1. 자칭 컨셉 | 사이트 메인·소개 텍스트 | 25% |
| 2. Vision | 시술 사진·기기 사진 | 30% |
| 3. 블로그 | 포스팅 키워드 빈도 | 20% |
| 4. 후기 | 후기·공공 데이터 키워드 | 25% |

- 4개 정렬 → 95%+ "확실"
- 일부 정렬 → 70~95% "추정"
- 자칭만 강하고 나머지 어긋남 → **자칭 도배 의심 페널티**
- 70% 미만 → "정보 부족"

## 분류 스키마 (M1 동결 필요)

표준 진료과목별 세부 4~6 분류. 김경재 DynamoDB 컬럼·인덱스, 하재원 컴포넌트 props의 기반이 되므로 변경 시 양쪽에 영향.

```
피부과     ├ 미용 시술 ├ 일반 진료(아토피·여드름) ├ 피부암·종양 └ 모발·탈모
정형외과   ├ 척추 ├ 어깨·견관절 ├ 무릎·관절 ├ 손·발(수부외과) └ 스포츠 의학
이비인후과 ├ 알레르기·비염 ├ 청각·이명 ├ 코·수면호흡 └ 갑상선
안과       ├ 라식·라섹 ├ 백내장 ├ 망막 └ 일반 시력
```

## S3 Vectors 메타데이터

쿼리 단계 필터링용. PutVectors 시 함께 적재:

`standard_specialty` / `primary_focus` (list) / `sido` / `sigungu` / `confidence_score` (>=) / `lat` (range) / `lng` (range) / `last_updated`

## 비용 의식

분류 1회 ~$0.05~0.20/병원. 1만 병원 PoC ~$500~2,000.

- 자칭이 매우 명확한 케이스는 `use_vision=False`로 절감
- Haiku 1차 분류 → Sonnet 검증 cascading 검토
- `MAX_VISION_IMAGES=10` 이상은 의식적으로

## 의존성·예외

각 함수가 던지는 예외는 `../docs/API-BE-AI.md` 참조: `BedrockInvocationError` / `InsufficientDataError` / `DescriptionValidationError` / `S3VectorsError` / `TextTooLongError` / `ImageNotFoundError`.

## 작업 원칙

- LangChain·LlamaIndex 같은 무거운 프레임워크 금지 — 4 시그널 로직을 명시적으로 통제해야 함
- Bedrock 호출은 반드시 mock 가능하게 (`@patch("ai.core.bedrock_client.invoke_model")`). 테스트가 실 호출 비용을 발생시키면 안 됨
- 의료법 표현은 `medical-language-reviewer` 서브에이전트에 검수 위임 가능
