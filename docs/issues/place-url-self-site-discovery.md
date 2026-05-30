# 이슈: 플레이스 공식 홈페이지/블로그 → `website_url` 보강 (자체 URL 없는 병원)

**상태:** 보류 (나중에 해결). 자체 블로그/사이트 반영은 우선순위 낮음 — 룰 기반 메타 분류로도
기본 커버는 됨. 네이버 raw 도착 후 함께 처리.

**관련:** `be/scripts/discover_official_blogs.py` (현행, 휴리스틱 한계 있음),
`be/scripts/ingest_naver_local.py`, `be/adapters/naver_place_adapter.py`,
`be/adapters/kakao_place_adapter.py`, `be/scripts/enrich_urls.py`.

## 문제

강남 3134개 중 **638개가 자체 홈페이지 `contact.website_url` 없음** → 사이트 크롤 불가 →
self_claim(자칭) 시그널 0. 이 병원들은 보통 별도 홈페이지 없이 **네이버 블로그/플레이스를
사실상 홈페이지로 운영**한다. 그 공식 채널을 찾아 `website_url` 로 승격하면 다음 크롤에서
self_claim 으로 흡수된다.

## 현행의 한계

### 1. `discover_official_blogs.py` — 빈도 휴리스틱이 불안정
- 이미 적재된 블로그 시드(NAVER#BLOG·KAKAO#BLOG)에서 `blog.naver.com/{ID}` 추출 →
  **같은 ID 가 ≥3회** 반복되면 "병원 자체운영 블로그"로 판정.
- **오탐**: 체험단·파워블로거가 한 병원 글을 3개 이상 쓰면 자체 블로그로 오인.
- **누락**: 병원 진짜 블로그인데 검색 API 색인 글이 3개 미만이면 못 잡음.
- 게다가 시드 모수가 **네이버 검색 API** 라 recall 이 낮음(병원명 검색이 공식 채널을 못 띄움).
- → 빈도 추측은 신뢰 못 함. 폐기 또는 보조로만.

### 2. 카카오 플레이스 — 638 갭을 못 메움 (실측)
```
강남 URL없음 638개
  ├ 카카오 플레이스 존재:  22개   (616개는 카카오에 아예 없음)
  │   └ 그중 홈페이지 URL: 2개 / blog.naver 포함: 0개
  └ 카카오 플레이스 없음: 616개
```
→ 카카오 단독으로는 거의 효과 없음. (URL 보유분의 카카오 홈페이지는 이미 enrich 됨.)

### 3. 네이버 플레이스 — 커버리지 넓지만 배선 없음
- 동네 의원 커버리지는 네이버 플레이스가 가장 넓음 → 638 갭의 실질적 희망.
- 그러나 현재 `ingest_naver_local.py` 는 **`NAVER#PLACE#REVIEWS`(후기)만 적재**.
  `parse_place()` 도 후기 파서라 **공식 홈페이지/블로그 필드를 추출하지 않음.**
- 즉 네이버 raw 가 들어와도 `website_url` 은 **자동으로 안 채워진다.**

## 제안 (권위 소스 = 플레이스 등록 공식 홈페이지/블로그 필드)

빈도 추측 대신 **플레이스가 직접 들고 있는 공식 채널 필드**를 쓴다 (사장님 등록값 = 권위 ·
회색지대 깨끗).

1. **네이버 플레이스 파서 확장**: place 패널에서 공식 홈페이지/블로그 링크 필드를 파싱
   (현 reviews-only → homepage 필드 추가). `ingest_naver_local` 에서 그 값으로
   `DynamoAdapter.update_website_url(hid, url)` 호출.
2. **카카오 플레이스 재활용**: `homepage_url`/`homepages_raw` 중 blog.naver 포함분도
   `_is_real_website` 가 허용하므로(이미), URL 없는 병원에 한해 승격. (효과는 22개 한정.)
3. **순위**: 일반 홈페이지 > 공식 블로그(blog.naver.com/{ID}, 플레이스가 명시한 것만).
   빈도 휴리스틱은 폐기하거나 위 둘이 모두 없을 때의 마지막 폴백으로만.
4. 승격된 URL 은 다음 크롤 사이클에서 자체사이트로 크롤 → self_claim 흡수.

## 비고
- 네이버 후기·플레이스 크롤은 로컬 PC(개인계정)에서 진행 중. raw JSON 도착 후 위 1번 배선.
- PoC 평가에 자체 URL 보강이 필수는 아님 → 데모 이후 처리.
