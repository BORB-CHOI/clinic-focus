# 이슈: 강남 미크롤 481 갭 — JS 렌더 하드 잔여물 + 크롤 브라우저 안정화

**상태:** 보류 (데모엔 불필요 — 기존 2286 크롤이 건강함). PoC 이후 또는 여유 시.

**관련:** `be/scripts/crawl_all.py`, `be/core/crawler.py`(JS 폴백·MIN_TEXT_THRESHOLD),
`be/core/browser_manager.py`(`--single-process`·MAX_PAGES_BEFORE_RESTART).

## 배경 — JS 렌더링은 이미 동작한다 (오해 정정)

요즘 병원 사이트는 React/Next.js 라 JS 렌더링이 필수. 크롤러는 이미 폴백을 갖춤:
`정적 httpx 본문 < MIN_TEXT_THRESHOLD(100자) → Playwright 렌더`. **실측으로 동작 확인됨.**

크롤된 2286개 샘플 300 실측:
- 메인 render_method: **static 234(78%) / playwright 66(22%)** → JS 폴백이 22% 에서 작동.
- 전체 텍스트 길이: 중앙값 **3161자**, 평균 9914자 → 90% 가 실질 콘텐츠 보유.
- 빈 껍데기(<300자): 29개(**10%**).

→ "정적=한물간 사이트만 크롤" 은 사실 아님. React/Next 도 상당수 렌더돼 들어가 있음.

## 문제 1 — 481 하드 잔여물 + 브라우저 과부하

강남 URL보유 2496 중 481 미크롤. 쉬운 사이트·Playwright 되는 사이트는 이미 2286 에
들어갔고, **남은 481 = 이전에 Playwright 로도 실패한 잔여물**(접속불가·도메인오류·
ERR_NAME_NOT_RESOLVED·이상 빌더). 이걸 `crawl_all --sigungu 강남구` 로 연달아 때리면:
- 4GB EC2 의 `--single-process` 헤드리스 크롬이 크래시 누적
  ("BrowserContext.new_page: Target page, context or browser has been closed" — ~7분에 6회).
- 연쇄 JS render 실패 → 저장 0. (개별 일회성 스크린샷은 멀쩡히 됨 — 지속 크롤 부하에서만 불안정.)

## 문제 2 — React 셸이 폴백을 못 타는 경우 (MIN_TEXT_THRESHOLD)

`MIN_TEXT_THRESHOLD=100` 이 낮아, React/Next 셸이 보일러플레이트 100~300자를 주면
폴백(Playwright)을 안 타고 "정적 성공"으로 저장됨 → 크롤된 2286 중 ~10%가 빈 껍데기
(self_claim 시그널이 부실). 단, Vision 데모는 페이지를 라이브 스크린샷으로 다시 보므로
시각 신호는 그래도 확보됨.

## 제안

1. **크롤 브라우저 안정화** (481 재시도 전): `--single-process` 해제(메모리 여유 확인 후)
   또는 `MAX_PAGES_BEFORE_RESTART 30→10`, JS render 실패 시 브라우저 재시작 후 1회 재시도.
2. **셸 감지 강화**: `MIN_TEXT_THRESHOLD 100→~500` 상향 + "루트 div 만 있고 본문 텍스트
   없음"(React 셸 패턴) 감지 시 강제 Playwright. → 문제 2 의 10% 빈 껍데기 회수.
3. 그 후 `crawl_all --sigungu 강남구` 재시도 → 481 중 살릴 수 있는 만큼.

## 비고
- 데모엔 불필요 — 기존 2286(JS 22%·실질 90%)으로 Vision 무작위 100 충분.
- 481 갭은 yield 낮은 하드 잔여물이라 비용 대비 효익 적음 → 보류.
