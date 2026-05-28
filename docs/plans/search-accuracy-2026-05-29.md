# 검색 정확도 개선 — 단어 사전·불용어·동의어 도입

**작성일**: 2026-05-29
**범위**: `ai/search/` 자연어 검색 파이프라인
**계기**: "사마귀 어디가 좋을까" 같은 자연어 쿼리에서 부정확한 병원이 추천되는 문제 보고

---

## 1. 진단 — 무엇이 문제였나

### 1.1 raw 쿼리를 그대로 임베딩

`ai/search/vector_store.py::_search_text_only` 의 핵심 로직이 단 한 줄이었다.

```python
vector = embed_text(query.query_text)  # 사용자 입력을 그대로 1024차원 벡터로
```

→ "어디가 좋을까", "추천해줘", "잘하는" 같은 검색 의도 표현이 임베딩에 노이즈로 박힘.
의미는 없는데 cosine 유사도를 흐리는 신호가 됨.

### 1.2 한국어 의학 동의어 갭

`docs/setup/aws-onboarding.md` 라인 370-377 에 측정값이 이미 있었다.

> Titan v2 의료 동의어 유사도 마진 좁음 — `사마귀 치료` ↔ `심상성 우췌 냉동요법`
> cos = 0.2507, 무관 도메인 대조군 0.1937 (갭 0.06뿐).
> 한국어 의학 학명에 약하다는 신호.

→ 병원 본문에 "심상성 우췌"로 적혀 있으면 사용자가 "사마귀"로 검색해도 못 찾음.
사전 단계에서 두 가지 대응책이 명시돼 있었지만 **둘 다 미구현 상태**였다.

| 대응 트랙 | 내용 | 이전 상태 |
|---|---|---|
| (A) | 동의어 사전을 KB ingest 전 본문에 주입 | 미구현 |
| (B) | 메타데이터 스키마에 `aliases: list[str]` 필드 추가 | 미구현 |

### 1.3 키워드 사전이 검색 시점에 안 쓰임

`ai/pipeline/classify.py::_KEYWORD_TO_FOCUS` 에 `사마귀 → 일반 진료(아토피·여드름)`
매핑이 있었지만, **분류 시점에만** 사용됐다. 검색 시점에는 활용 불가능 → 사용자가
`specialty=피부과` 를 명시하지 않으면 메타필터가 비어 정확도가 더 떨어짐.

### 1.4 PoC 4 진료과만 커버

기존 `_KEYWORD_TO_FOCUS` 와 `_SPECIALTY_KEYWORDS` 는 피부과·정형외과·이비인후과·안과
4개만 커버. `ai/CLAUDE.md` 에 명시된 22 표준 진료과목 중 18개가 빈 칸이었다.

---

## 2. 개선한 점 — 무엇을 어떻게 바꿨나

### 2.1 신규 모듈 — `ai/search/dictionaries.py`

데이터를 처리 로직과 분리했다. 사전이 커져도 운영 코드는 그대로.

| 상수 | 용도 | 규모 |
|---|---|---|
| `STOPWORDS` | 검색 의도 표현 제거. "어디", "추천", "좋은", "잘하는", "병원" 등. | ~80개 |
| `SYNONYMS` | 의학 동의어 (단방향: 사용자 입력어 → 본문 학명·전문용어). `사마귀 → [심상성 우췌, verruca, 냉동치료, ...]` 형태. | 60+ 키, 200+ 동의어 |
| `KEYWORD_TO_SPECIALTY` | 의료 키워드 → 22 표준 진료과목 매핑. 강남 502 실측 키워드(`body-keywords-2026-05-27.json`) 통합. | 100+ 키워드 |
| `KEYWORD_TO_FOCUS` | `primary_focus` 추출용 (자유 문자열, 메타필터 아님). | 40+ 키워드 |
| `VALID_SPECIALTIES` | 22 후보 화이트리스트. 추론 결과 검증. | 22 |

**원칙**:
- `STOPWORDS` 에는 의료 용어를 절대 포함하지 않음 (임베딩 의미 신호 손실 방지).
- `SYNONYMS` 는 단방향. `사마귀 → 심상성 우췌` 만 채우고 역방향은 안 채움.
  병원 본문에서 사용자 표현으로의 매핑은 임베딩이 흡수하라는 의미.
- 의료법 광고 회색지대 형용사("잘하는", "전문") 는 동의어 사전에 절대 포함 안 함.

### 2.2 신규 모듈 — `ai/search/query_processor.py`

7 단계 파이프라인을 단일 진입점 `process_query(str) -> ProcessedQuery` 로 묶었다.

```
사용자 입력
  ↓ normalize_query        (특수문자·공백·대소문자 정리)
  ↓ tokenize               (공백 단위)
  ↓ strip_stopwords        (검색 의도 표현 제거 + 의료 키워드 보호)
  ↓ extract_medical_terms  (사전 매칭, multi-word 우선, 부분문자열 dedup)
  ↓ infer_specialty        (절대 다수결 50% 초과 시에만 확정)
  ↓ infer_focus            (primary_focus 후보 추출)
  ↓ expand_with_synonyms   (의학 동의어 부착)
  → ProcessedQuery (medical_terms / inferred_specialty / embedding_text / ...)
```

**핵심 안전 장치**:

| 장치 | 목적 |
|---|---|
| 의료 키워드 보호 | `strip_stopwords` 에서 사전 등록 키워드는 조사 분리 대상에서 제외. "코골이 → 코골" 같은 손상 방지. |
| 모호성 가드 | `infer_specialty` 가 1위 점유율 ≤ 50% 면 None 반환. 동률·박빙에서 잘못된 메타필터 차단. |
| Fallback 안전 | 매칭 0건이어도 정규화된 원문이 `embedding_text` 에 들어가 검색이 굴러감. |
| 사용자 우선 | 추론된 specialty 는 사용자가 `specialty` 를 안 줬을 때만 적용. |

### 2.3 `vector_store.py` 통합

`_search_text_only` 와 `_search_hybrid` 진입 직후에 `process_query` 를 끼워 넣었다.

**Before**:
```python
vector = embed_text(query.query_text)
meta_filter = _build_meta_filter(
    sido=query.sido, sigungu=query.sigungu,
    specialty=query.specialty,                 # 사용자 명시 안 하면 None
    min_confidence=query.min_confidence,
)
```

**After**:
```python
processed = process_query(query.query_text or "")
vector = embed_text(processed.embedding_text or query.query_text or "")

effective_specialty = query.specialty or processed.inferred_specialty
meta_filter = _build_meta_filter(
    sido=query.sido, sigungu=query.sigungu,
    specialty=effective_specialty,             # 자동 추론 보강
    min_confidence=query.min_confidence,
)
# ...
interpretation = _build_interpretation(processed) if processed.medical_terms else None
```

**위치 단독 검색(`_search_location_only`) 은 손대지 않음** — 자연어 쿼리가 없으므로
전처리 대상이 아님.

**Fallback 시에도 자동 추론 specialty 풀어주기**: 결과 0건일 때 `effective_specialty`
도 함께 풀어서 메타필터 완화. `query_text` 만 임베딩 검색으로 다시 호출.

### 2.4 응답에 `query_interpretation` 채우기

기존엔 항상 `None` 이었음. 이제 추출된 키워드와 추론 결과를 사용자가 볼 수 있는
형태로 묶어 보냄.

```
입력: "사마귀 어디가 좋을까"
응답 query_interpretation: "사마귀 · 진료과: 피부과 · 분야: 일반 진료(아토피·여드름)"
```

→ FE 가 검색 결과 상단에 "이렇게 이해했어요" 박스로 노출하면 사용자가 오해석을
즉시 인지하고 재검색 가능.

### 2.5 ai 패키지 export

`ai/__init__.py` 의 lazy import 맵에 `process_query`, `ProcessedQuery` 추가.
BE 가 `from ai import process_query` 로 직접 사용 가능 (FE 미리보기 등 용도).

### 2.6 단위 테스트 신규 작성

`ai/tests/test_query_processor.py` — 19 테스트 케이스. boto3 의존 없어 즉시 실행 가능.

| 테스트 클래스 | 검증 |
|---|---|
| `TestNormalizeQuery` (5) | 특수문자·공백·대소문자·의료 표기 보존 |
| `TestTokenization` (4) | 의도 표현 제거, 의료 키워드 조사 보호 |
| `TestExtractMedicalTerms` (5) | 단·다중 키워드, multi-word 우선, dedup |
| `TestInferSpecialty` (6) | 단독·다수결·모호·미지·화이트리스트 검증 |
| `TestInferFocus` (2) | focus 추출 + dedup |
| `TestSynonymExpansion` (3) | 확장·중복 회피·매칭 0건 |
| `TestProcessQuery` (4 + 5 매트릭스) | 회귀 방지 — "사마귀 어디가 좋을까" 명시 + 진료과 매트릭스 |

`ai/tests/__init__.py` 도 함께 생성 (해당 디렉토리에 기존 테스트가 없었음).

### 2.7 동작 변화 — 핵심 케이스

| 입력 | 의료 키워드 | 추론 진료과 | 동의어 확장 (발췌) |
|---|---|---|---|
| `사마귀 어디가 좋을까` | `[사마귀]` | 피부과 | 심상성 우췌, verruca, 냉동치료 |
| `허리 디스크 잘하는 곳` | `[허리, 디스크]` | 정형외과 | 요추, 요통, 추간판 탈출증 |
| `코골이 수면 무호흡 검사` | `[코골이, 수면 무호흡]` | 이비인후과 | 수면호흡장애, 코골이 수술 |
| `당뇨 고혈압 관리` | `[당뇨, 고혈압]` | 내과 | 당뇨병, 제2형 당뇨, 본태성 고혈압 |
| `라식 사마귀` (모호) | `[라식, 사마귀]` | None | (확장은 함, 메타필터는 안 걺) |
| `그냥 평범한 문장` | `[]` | None | 원본 그대로 임베딩 (안전 fallback) |

10/10 sanity check 통과 확인.

---

## 3. 추가 보완 사항

### 3.1 단기 (현 PR 후속)

#### 3.1.1 BE 검색 API 연결

`be/api/search.py` 라인 56-73 가 자연어 쿼리에 빈 데이터 + "AI 모듈 연동 후 지원"
메모를 반환하는 stub 상태. `from ai import search_similar` 를 호출하도록 교체 필요.
이번 PR 범위 밖이지만 검색 정확도 개선 효과를 사용자가 보려면 필수.

#### 3.1.2 Fallback 정책 재검토

현재 결과 0건 시 사용자가 명시한 `sido`/`sigungu`/`specialty` 까지 모두 풀어버림.
사용자 의도와 어긋날 수 있음.

대안:
- 1차 fallback: 자동 추론 specialty 만 풀고 사용자 명시 필터는 유지
- 2차 fallback: 그래도 0건이면 사용자 specialty 도 풀기
- 3차 fallback: 지역까지 풀기

`SearchQuery` 에 `fallback_strategy: Literal["strict", "expand_specialty", "expand_all"]`
필드 추가 검토.

#### 3.1.3 동의어 사전 확장

현 60+ 키는 메이저 진료과 위주. 다음 영역이 빈약:
- 한의원 (추나·한약·침 외 비어있음 — 한방 진단명 추가 필요)
- 치과 (임플란트·교정·충치·잇몸 외 비어있음)
- 산부인과 (임신·자궁·월경 정도)
- 비뇨의학과 (전립선·요로 정도)

medical-language-reviewer 에이전트 검수 거쳐 진료과별로 20-30개씩 확장 권장.

#### 3.1.4 KEYWORD_TO_SPECIALTY 의 multi-word 매핑

현재 `"수면 무호흡": ["이비인후과"]` 처럼 multi-word 키도 있지만 대부분 single-word.
`"여드름 흉터"`, `"안드로겐성 탈모"` 같은 합성어를 추가하면 정확도 추가 상승 가능.

#### 3.1.5 사전 단일 출처화

`ai/pipeline/classify.py::_KEYWORD_TO_FOCUS` 와 `ai/search/dictionaries.py::KEYWORD_TO_FOCUS`
가 현재 비슷하지만 다른 사전으로 공존한다. 의도된 분리(분류 시점 vs 검색 시점)지만,
한쪽만 갱신되면 분류 결과와 검색 추론이 어긋날 위험. 다음 PR 에서 단일 모듈로 통합
또는 한쪽이 다른 쪽을 import 하는 구조로 정리 필요.

### 3.2 중기 (다음 스프린트)

#### 3.2.1 KB Retrieve 마이그레이션과의 정합

`ai/CLAUDE.md` 와 `README.md` 는 "Bedrock Knowledge Base 경유로 전환 결정 (2026-05-24)"
으로 적혀 있지만 실제 코드는 S3 Vectors 직접 호출. `kb_store.py` 가 미구현 상태.

KB 전환 시 본 PR 의 query_processor 는 그대로 재사용 가능하지만 **메타데이터 스키마**
가 바뀌므로 재검증 필요:
- KB 메타데이터에 `aliases: list[str]` 필드를 추가하면 (B 트랙) 본문 동의어 주입 없이도
  검색 매칭률이 더 올라감.
- `team_id` 필수 필드와 `KEYWORD_TO_SPECIALTY` 화이트리스트 정합 확인.

#### 3.2.2 사전을 JSON 으로 외부화

지금은 Python dict 로 박혀 있어 사전 갱신마다 코드 변경 필요.
`ai/data/dictionaries/{stopwords.json, synonyms.json, keyword_to_specialty.json}`
형태로 분리하면:
- 의료 전문가가 GitHub PR 로 사전만 수정 가능
- 운영 중 사전 갱신을 hot reload 가능 (Lambda 패키지 재빌드 불필요)

`dictionaries.py` 는 JSON loader + 캐시만 담당하게 변경.

#### 3.2.3 검색 평가 데이터셋 구축

현재 정확도 회귀 검증은 단위 테스트의 매트릭스 5건뿐. 운영 정확도를 측정하려면:
- 의료 전문가 라벨링한 (쿼리, 정답 병원 ID) 50-100쌍
- nightly 평가 스크립트가 top-1 / top-5 / mean reciprocal rank 측정
- 사전 PR 머지 전 기준선 대비 회귀 자동 차단

`ai/scratch/measure_*.py` 컨벤션 따라 `ai/scratch/measure_search_accuracy.py` 추가.

#### 3.2.4 형태소 분석기 도입 검토

현재 토크나이저는 공백 분리 + 1글자 조사 제거 휴리스틱. 한국어 합성어("코골이",
"피부과") 는 잘 처리되지만 활용형("디스크에", "디스크가") 은 일부만 잡힘.

도입 시 후보:
- **kiwi-py** — 순수 Python, Lambda 패키징 OK, 의료 도메인 사전 추가 가능
- **mecab-ko** — 정확도 최고지만 Lambda Layer 빌드 복잡
- **현 휴리스틱 유지** — 사전 규모로 보완 가능하면 외부 의존성 추가 안 하는 게 가벼움

먼저 평가 데이터셋(3.2.3) 으로 휴리스틱의 한계를 정량화하고 결정 권장.

### 3.3 장기 (운영 안정화 후)

#### 3.3.1 사용자 피드백 기반 사전 자동 갱신

`SearchFeedback` 모델은 이미 있음 (`ai/search/feedback.py`).
- 사용자가 클릭한 결과의 본문 키워드를 분석 → 새 동의어 후보 발굴
- 클릭률이 낮은 쿼리 추적 → 사전이 못 잡은 패턴 식별

월간 사전 갱신 자동화로 도메인 전문가 부담 감소.

#### 3.3.2 의료법 회색지대 검수 자동화

현재 `STOPWORDS` 와 `SYNONYMS` 는 수동 검수. 동의어가 광고성 표현("최고의 효과",
"빠른 회복") 을 포함하면 **검색 결과 자체가 의료법 회색지대를 끌어당김**.

medical-language-reviewer 에이전트로 사전 PR 자동 검수:
- "잘하는", "전문", "탁월", "최고" 등 평가 형용사 자동 차단
- 의료광고 가이드라인 위반 표현 차단

#### 3.3.3 다국어 지원

영어 쿼리 일부는 `_ASCII_UPPER` lowercase 만 처리됨. 한국 거주 외국인용 영어 쿼리
("LASIK clinic near me") 가 늘어나면:
- `STOPWORDS` 영어 셋 확장
- `SYNONYMS` 영어 키 추가 (`wart → [verruca, 사마귀, ...]`)
- 영어 쿼리 감지 → 영어 동의어로 한국어 본문 매칭

---

## 4. 변경 파일 목록

### 4.1 추가된 파일 (5)

| 경로 | 역할 | 주요 심볼 |
|---|---|---|
| `ai/search/dictionaries.py` | 검색 사전 데이터 — 처리 로직과 분리. JSON 외부화 시 본 모듈은 loader 만 남김. | `STOPWORDS`, `SYNONYMS`, `KEYWORD_TO_SPECIALTY`, `KEYWORD_TO_FOCUS`, `VALID_SPECIALTIES` |
| `ai/search/query_processor.py` | 쿼리 정제·확장 파이프라인. 7 단계 처리 후 `ProcessedQuery` 반환. | `ProcessedQuery`, `process_query`, `normalize_query`, `tokenize`, `strip_stopwords`, `extract_medical_terms`, `infer_specialty`, `infer_focus`, `expand_with_synonyms` |
| `ai/tests/__init__.py` | `ai` 패키지에 테스트 디렉토리가 없었음 — 새로 초기화. | (빈 파일) |
| `ai/tests/test_query_processor.py` | query_processor 단위 테스트. boto3 의존 없어 즉시 실행 가능. | `TestNormalizeQuery`, `TestTokenization`, `TestExtractMedicalTerms`, `TestInferSpecialty`, `TestInferFocus`, `TestSynonymExpansion`, `TestProcessQuery` (총 19 케이스) |
| `docs/plans/search-accuracy-2026-05-29.md` | 본 작업 노트 — 진단·개선·보완사항 정리. | (본 문서) |

### 4.2 수정된 파일 (2)

| 경로 | 변경 내용 |
|---|---|
| `ai/search/vector_store.py` | • `import` 에 `from ai.search.query_processor import ProcessedQuery, process_query` 추가<br>• `_search_text_only` — `embed_text(query.query_text)` 한 줄 → `process_query` → `embed_text(processed.embedding_text)` 흐름으로 교체. `effective_specialty = query.specialty or processed.inferred_specialty` 메타필터 보강. fallback 분기 조건도 `effective_specialty` 반영.<br>• `_search_hybrid` — 동일 패턴 적용. 자연어 임베딩 직전에 `process_query` 호출.<br>• `_search_location_only` — **변경 없음** (자연어 쿼리 미사용).<br>• `_build_interpretation(processed)` 헬퍼 신규 추가. `query_interpretation` 응답 필드 채움. |
| `ai/__init__.py` | • lazy import 맵 `_module_map` 에 `process_query`, `ProcessedQuery` 두 항목 추가.<br>• `TYPE_CHECKING` 블록과 `__all__` 리스트에도 함께 등재. |

### 4.3 변경 없음 (확인만)

다음 파일들은 본 PR 범위로 검토했지만 변경하지 않음:

| 경로 | 이유 |
|---|---|
| `ai/pipeline/classify.py` | 분류 시점의 `_KEYWORD_TO_FOCUS` 는 그대로 유지. 검색 시점 사전은 별도 모듈로 분리 (책임 분리 원칙). |
| `ai/search/embed.py` | Titan v2 래퍼. 입력 텍스트만 정제된 형태로 들어가므로 함수 시그니처 변경 불필요. |
| `ai/search/related.py` | `find_related_hospitals` 가 내부적으로 `search_similar` 호출 → 자동으로 query_processor 효과 받음. |
| `be/api/search.py` | 자연어 검색 stub 상태. AI 모듈 연결은 별도 PR (3.1.1 참조). |
| `shared/models.py` | `SearchQuery`/`SearchResult` 스키마 변경 불필요. `query_interpretation` 필드는 이미 정의돼 있었음. |

---

## 5. 검증 절차

```bash
# 1. 진단 — 정적 분석
# (Kiro 의 getDiagnostics 도구로 5 파일 모두 무결 확인)

# 2. 단위 테스트
pytest ai/tests/test_query_processor.py -v

# 3. 핵심 케이스 sanity check (본 작업 중 10/10 통과 확인)
#    "사마귀 어디가 좋을까" → 피부과 추론 + 동의어 확장
#    "허리 디스크" → 정형외과 추론
#    "코골이" → "코골이" 보존 (조사 분리 사고 없음)
#    "라식 사마귀" → 모호 → None (잘못된 메타필터 안 걺)

# 4. 통합 테스트 (BE search API 연결 후)
#    실제 S3 Vectors 인덱스 대상 검색 정확도 측정
```

---

## 6. 결론

**근본 원인**: raw 쿼리를 그대로 임베딩 + 의학 동의어 갭 + 키워드 사전 미활용.

**개선의 핵심**: 임베딩 호출 직전에 사전 기반 정제·확장 단계를 끼워 넣고, 메타필터에
자동 추론 specialty 를 보강. 데이터(사전) 와 로직(처리) 을 분리해 향후 확장이 쉬움.

**위험 관리**: 모든 단계에 fallback 안전 장치를 박아 사전이 빈약해도 검색이 0건이
되는 사고 방지. 모호 추론은 None 처리해서 잘못된 메타필터로 결과를 좁히지 않음.

**다음 작업**: BE search API stub 연결 + 동의어 사전 확장 (한의원/치과/비뇨의학과
중심) + 평가 데이터셋 구축.
