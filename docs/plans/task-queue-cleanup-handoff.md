# task-queue.md 정리 핸드오프 (2026-05-26)

이 메모는 **새 세션이 task-queue.md를 정리할 때 컨텍스트 없이 시작할 수 있도록** 만든 것. 작업 끝나면 이 파일도 삭제.

## 목표

`docs/plans/task-queue.md` 가 416줄로 비대해졌고, "다음 PR 순서" 섹션(L54-176)과 "AI 트랙 AWS 세팅 todo Step 6"(L287-374)이 같은 일을 두 곳에 적어두는 중복 상태. **GitHub 이슈가 생긴 항목은 이슈 링크로 대체하고, 우리 트랙(AI) 작업이 Step 6 한 곳에 집중되도록** 청소.

## 현재 사실 (정리 작업의 인풋)

### 발행된 GitHub 이슈 (BE 위임)
- **#13** — feat(be): HTML 크롤링 잡음 정제 추가 + hash diff 기반 갱신 구조
- **#18** — feat(be): 병원 목록 소스 전략 + 외부 시그널 크롤러 부재
- **#23** — feat(be): AI 트랙 e2e 대응 — `s3_adapter` boto3 + `crawl_all` TABLE_PREFIX
- **#24** — bug(be): `be/scripts/_utils.load_env`가 인라인 주석을 값에 포함시킴

### "다음 PR 순서" → 이슈 매핑 결과
| PR # in task-queue | 현재 상태 |
|---|---|
| #1 `feat/ai/aws-clients` | 오늘 부분 수정됨 (Bedrock 개인 계정 통합, 커밋 `921fd7f`) |
| #2 `feat/be/test-fix` | 손 안 댐. BE 일정 |
| #3 `feat/be/clean-noise` | 이슈 #13 으로 위임됨 |
| #4 `feat/ai/track-a-rule-classifier` | 미시작 (룰 분류 트랙 A) |
| #5 `feat/ai/track-bc-llm-vision-demo` | 오늘 `ai/scratch/classify_all.py`로 사실상 초기 진척. Step 6과 사실상 동일 |
| #6 `feat/be/hash-diff-foundation` | 이슈 #13 후반부로 위임됨 |
| #7 `feat/be/crawl-seoul-5gu-full` | 이슈 #18 로 위임됨 |

### Step 6 — AI 개인 dev 계정 e2e (L287-374) 현 상태
| Step | 상태 |
|---|---|
| 6-1 DDB 7테이블 수동 생성 | ✅ 완료 (2026-05-26) |
| 6-2 S3 버킷 생성 | ✅ 완료 (2026-05-26) |
| 6-3 S3Adapter boto3 전환 + crawl_all prefix 패치 | ⏭️ BE 위임 (이슈 #23) |
| 6-3a AI 트랙 우회 (`ai/scratch/`) | 🚧 진행 중 — load_dev_subset/crawl_all_ai/classify_one/classify_all 작성됨 |
| 6-4 28개 → S3 마이그레이션 | ❌ 폐기 (28개 ykiho는 BE 계정용이라 매핑 불가, 85개로 새로 시작) |
| 6-5 HIRA 강남구 4과목 ~85개 적재 | ✅ 완료 (88개 DDB 적재) |
| 6-6 85개 미니 크롤링 | ✅ 완료 (URL 보유 25개 / 성공 14개) |

## 정리 작업 가이드

1. **"다음 PR 순서" (L54-176) 전체를 짧은 매핑 표로 압축**
   - #3, #6, #7 → 이슈 #13/#18 링크로 한 줄씩
   - #5 → Step 6과 동일하니 Step 6 본문 가리키는 한 줄로 대체
   - #1, #2, #4 만 남기되 진척 상태 갱신
2. **Step 6 본문은 그대로 두기** — 우리 트랙 핵심 기록
3. **L383+ "완료된 작업"은 손대지 말 것** — 머지 PR 히스토리

## 조심할 것

- **main 브랜치 직접 수정 금지** — feature 브랜치 만든 후 작업 (`.claude/settings.json` PreToolUse hook이 차단). 브랜치 이름 예: `docs/task-queue-cleanup`
- 작업 끝나면 이 핸드오프 메모(`docs/plans/task-queue-cleanup-handoff.md`) 도 같이 삭제하는 커밋 포함
- BE 담당자(김경재)의 큐와는 무관 — 우리 트랙(AI) 시각에서 정리

## 시작 명령 예시 (새 세션에)

```
docs/plans/task-queue-cleanup-handoff.md 를 따라 task-queue.md 청소해줘.
```
