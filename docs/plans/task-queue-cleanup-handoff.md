# V2 진입을 위한 문서·계획 정리 핸드오프 (2026-05-26)

이 메모는 **새 세션이 V2 로드맵을 짜기 전 문서 정합성과 진짜 작업 범위를 잡을 수 있도록** 만든 것. 모든 항목 끝나면 이 파일도 삭제.

> V2 정의 (사용자 확인): "갈아엎고 끝까지 다 구현". `ai/scratch/` 임시 폴더 통째 삭제하고 본체 함수로 정식 구현 + BE API 4개 본체 동작 + FE 화면 완성 + 4 시그널 다 켜기.

## 작업 4가지 — 순서 권장

### 1. docs/plans/task-queue.md 청소

원래 메모의 본 목적. **task-queue.md 가 416줄로 비대 + PR 큐 섹션이 이슈로 옮겨진 항목과 중복**. 그동안 발행된 이슈로 매핑·정리.

기존 PR 큐 → 이슈 매핑 (확정):
| 큐 | 상태 |
|---|---|
| PR #1 `feat/ai/aws-clients` | 부분 진척 (오늘 Bedrock 개인 계정 통합) |
| PR #2 `feat/be/test-fix` | BE 일정, 손 안 댐 |
| PR #3 `feat/be/clean-noise` | 이슈 [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13) 로 이관 |
| PR #4 `feat/ai/track-a-rule-classifier` | 미시작 (룰 분류 트랙 A) |
| PR #5 `feat/ai/track-bc-llm-vision-demo` | 오늘 PR [#25](https://github.com/BORB-CHOI/clinic-focus/pull/25) 가 초기 진척 |
| PR #6 `feat/be/hash-diff-foundation` | 이슈 [#13](https://github.com/BORB-CHOI/clinic-focus/issues/13) 후반부 |
| PR #7 `feat/be/crawl-seoul-5gu-full` | 이슈 [#18](https://github.com/BORB-CHOI/clinic-focus/issues/18) 로 이관 |

신규 발행된 BE 위임 이슈:
- [#23](https://github.com/BORB-CHOI/clinic-focus/issues/23) `s3_adapter` boto3 + `crawl_all` `TABLE_PREFIX`
- [#24](https://github.com/BORB-CHOI/clinic-focus/issues/24) `be/scripts/_utils.load_env` 인라인 주석 버그

### 2. docs/plans/be-aws-wiring.md → task-queue.md 흡수

`be-aws-wiring.md` 의 B1~B13 큐 중 상당수가 이미 이슈로 옮겨졌거나 완료됨. **별도 파일로 두는 의미가 사라짐**. task-queue.md 의 BE 섹션으로 흡수 후 `be-aws-wiring.md` 삭제.

매핑 (실측 필요):
- B1 (DDB 7테이블) ✅ 완료 (AI 트랙 콘솔에서 함, 2026-05-26)
- B4 (S3 버킷) ✅ 완료 (`kmuproj-10-clinic-focus-crawl`)
- B5 (S3Adapter boto3) → 이슈 #23
- B8 (잡음 정제) → 이슈 #13
- B11-pre (`crawl_all.py` TABLE_PREFIX) → 이슈 #23
- 나머지는 BE 트랙 그대로

### 3. deploy/ + docs/setup/aws-onboarding.md 위치 정리

세 자료가 EC2 운영·온보딩 관련이지만 위치가 분산:
- `deploy/` (repo root) — systemd + setup.sh + ssh 접속 명령
- `docs/setup/aws-onboarding.md` — 신규 팀원 EC2 접속 → 자원 확인 → DDB 생성 절차 (Step 0~7)
- `docs/plans/be-aws-wiring.md` — BE 작업 큐 (#2 와 겹침)

권장 통합:
- `deploy/` 폴더 유지 (코드/스크립트라 root 가 자연스러움) + `deploy/README.md` 를 `docs/setup/ec2-deploy.md` 로 이전, `deploy/README.md` 는 `docs/setup/ec2-deploy.md` 가리키는 짧은 stub
- `docs/setup/aws-onboarding.md` 의 Step 6·7 (DDB·S3 생성) 은 이미 완료 — 완료 마크 + 다음 팀원 재현용으로만 유지
- 결과: 신규 팀원이 보는 진입점은 `docs/setup/aws-onboarding.md` 한 곳

### 4. V2 로드맵 작성 ⭐ 진짜 본업

#### V2 = "본 서비스 9가지 차별점 모두 동작"

`docs/overview.md` 와 `docs/dev-roadmap.md` 가 정의하는 본 서비스 기능을 V1 (오늘까지) 와 매트릭스로 대조:

| # | 기능 | 출처 | 현 상태 |
|---|---|---|---|
| 1 | 자연어 검색 (KB Retrieve) | `overview.md` 4-5 | ✅ AI dev e2e 통과 |
| 2 | 상세 페이지 9개 영역 | `overview.md` 148-214, `API-FE-BE.md` 2번 엔드포인트 | ❌ FE 미시작, BE API 미구현 |
| 3 | AI 통합 상세 설명 ⭐ | `overview.md` 4-4 | △ 동작하지만 출처 시그널·약점 단락 검증 미흡 |
| 4 | 4 시그널 교차 검증 | `overview.md` 5-1 | △ 자칭만, Vision/블로그/후기 = 0% |
| 5 | 신뢰도 + 피드백 자기교정 | `overview.md` 5-2 | ❌ `recompute_confidence`·`aggregate_feedback_stats` 미구현 |
| 6 | 분류 변경 이력 자동 기록 | `overview.md` 10-3, `API-FE-BE.md` 3번 | ❌ 테이블만 있고 로직 없음 |
| 7 | 피드백 (디바이스ID 중복방지) | `API-FE-BE.md` 4번 | ❌ 미구현 |
| 8 | 관련 병원 추천 | `API-FE-BE.md` 상세 영역 7 | △ 코드 있고 실측 미흡 |
| 9 | 카테고리 이중 색인 (다루지 않는 분야 명시) | `overview.md` 4-2 | △ `extract_services_and_doctors` 코드 있고 실측 미흡 |

#### V2 작업 — 트랙별

**AI 트랙 (본체화 + 미구현 함수 + 시그널 보강)**:
- `ai/scratch/` 7개 파일 → `ai/` 본체로 마이그레이션 후 폴더 삭제 (이슈 #23 머지 의존)
- `ingest_hospital`·`retrieve_hospital` 정식 구현 (현재 scratch 우회)
- `index_hospital` (옛 S3 Vectors) 코드 제거 — `ingest_hospital` 로 대체
- `extract_services_and_doctors` 실측 검증 + "다루지 않는 분야" 정확도
- `find_related_hospitals` 실측 검증
- `recompute_confidence` 구현 (피드백 반영 자기교정 루프)
- `aggregate_feedback_stats` 구현
- 신뢰도 로직 약점 수정: `primary_focus=[]` + `confidence=100` 케이스
- 분류 변경 자동 기록 (`ChangeHistory` 테이블에 hash diff 시 INSERT)
- Vision 모델 access 활성화 (개인 계정 Marketplace 구독)
- 표본 확장 (14개 → 5개구 1만 또는 최소 100개)

**BE 트랙**:
- 이슈 #23 (s3_adapter boto3 + crawl_all prefix) — AI 트랙 본체화의 차단 요인
- 이슈 #24 (load_env 인라인 주석 버그)
- 이슈 #13 (HTML 잡음 정제 + hash diff 갱신 구조) ⭐ 분류 품질 직접 영향
- 이슈 #18 (병원 목록 소스 + 외부 블로그·후기 크롤러) ⭐ 4 시그널 완성
- FastAPI 4개 엔드포인트 본체 구현 (`/api/search` · `/api/hospitals/{id}` · `/api/hospitals/{id}/history` · `/api/feedback`)
- 단일테이블 vs 7-table 결정·정합 (BE 담당자 운영 중)
- DynamoDB `ChangeHistory` 적재 로직 (분류 변경 시 자동 INSERT)
- 피드백 디바이스ID 중복 방지 (`check_duplicate_feedback` 활용)

**FE 트랙**:
- 검색 결과 페이지 (자연어 입력 → 결과 카드 목록, TanStack Query)
- 상세 페이지 9개 영역 (각각 다른 UI 패턴)
- 피드백 UI (👍/👎 익명, localStorage 디바이스ID)
- 분류 변경 이력 표시 UI
- OpenAPI TS 타입 자동 생성 동기화 (`openapi-typescript`)

**공통**:
- 의료법 회색지대 표현 전수 검수 (`medical-language-reviewer` 서브에이전트)
- `shared/models.py` 모델 변경 시 BE·AI 동시 갱신 확인

#### V2 마일스톤 (3~4주)

`docs/dev-roadmap.md` Phase 1 (M0~3 PoC) 매트릭스를 V2 sprint 로 압축:

| 주 | AI | BE | FE |
|---|---|---|---|
| 1 | scratch → 본체 마이그레이션, 미구현 함수 시그니처 | 이슈 #23/#24 처리, API 4개 skeleton | 검색 결과 페이지 |
| 2 | extract/related/feedback 함수 본체 + 실측 | API 4개 본체 + DDB 적재 로직 | 상세 페이지 9영역 |
| 3 | 시그널 보강 (Vision 활성화, 이슈 #18 머지 후 블로그/후기) | 이슈 #13 정제 + hash diff | 피드백 UI + 변경 이력 |
| 4 | 표본 확장 + 전체 통합 e2e | 의료법 표현 검수 | 폴리싱 |

## 시작 명령 예시 (새 세션에)

작업 1 (task-queue 청소)·2 (be-aws-wiring 흡수)·3 (deploy/aws-onboarding 정리)·4 (V2 로드맵) 순서. 1~3 끝나면 task-queue.md 가 깨끗한 V2 sprint 계획서 됨.

```
docs/plans/task-queue-cleanup-handoff.md 를 따라 V2 진입 작업 시작해줘.
순서는 1→2→3→4. 각 단계 끝나고 사용자 확인 받고 다음으로.
```

## 주의

- main 브랜치 직접 수정 금지 (PreToolUse hook 차단). 작업당 별도 브랜치
- BE 본체 코드 수정은 BE 담당자(김경재) 영역 — AI 트랙이 단독 수정 금지. 이슈로 위임
- 통합 완료 시 이 핸드오프 메모도 삭제 커밋 포함
