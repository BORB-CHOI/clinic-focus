# 외부 플랫폼 크롤 실측 노트 (네이버·카카오, 2026-05-28)

> 원래 [`task-queue.md`](task-queue.md) Phase B 의 raw 노트 박스였으나, 작업 큐를
> "남은 작업"만 남기기 위해 본 문서로 이전(2026-05-28 정리). 네이버·카카오
> 플레이스 비공식 엔드포인트 실측 · robots/약관 · GraphQL 스키마 · PII 노출 ·
> 운영 비용 · Vision 입력 전략 결정이 사실(fact) 단위로 박혀 있음. probe 재현
> 코드는 scratch 제거와 함께 삭제됐고(샘플은 `be/tests/fixtures/{kakao,naver}` 로
> 본체화), 아래 raw 사실이 그 자리를 대신한다.
>
> ⚠️ robots Disallow + 약관 자동화 금지 검토 결과는 task-queue Phase B 의
> "실제 크롤 실행" 항목과 직결 — 네이버·카카오 실행 여부는 운영자(사용자) 결정.
> 구글 Places·네이버 블로그 공식 API 는 합법.

---

> ⚠️ **Phase B 진입 전 결정 — 후기 시그널 전략** (2026-05-27 추가, 다음 세션 1순위 의제)
>
> 본 박스는 **플레이스·후기 데이터 자체 수집**에 관한 것. BE PR [#21](https://github.com/BORB-CHOI/clinic-focus/pull/21) 의 "URL 보강 크롤링"(네이버·카카오 검색 결과 페이지에서 병원의 자체 홈페이지 URL 추출 — 자칭 시그널 시드용)과는 **별개**. 같은 "네이버·카카오" 단어라 혼동하기 쉬움 — PR #21 은 자체 사이트 시드 확보 → 본 박스는 외부 후기 본체 수집.
>
> 4 시그널 中 후기(25%) 는 본 서비스 핵심 차별점인데, 공식 API 로는 **구글 Places (Reviews 5건/병원)** 만 합법 커버 가능. 네이버 플레이스·카카오맵 리뷰는 **비공식 엔드포인트** 만 존재. 사용자 실측(2026-05-27 브라우저 네트워크 캡처)으로 확인된 네이버 엔드포인트:
>
> | 호출 | 엔드포인트 | 응답 |
> |---|---|---|
> | 카테고리 검색 | `GET map.naver.com/p/api/search/allSearch?query=병원&searchCoord=...&boundary=...` | place_id · 이름 · 주소 · 카테고리 · 좌표 · `reviewCount` · `placeReviewCount` · 영업시간 · 썸네일 · 홈페이지 |
> | 세션 토큰 | `POST ncpt.naver.com/v2/tokens?q={ts}&tid={...}` | (필수성 미검증 — 토큰 없이도 동작하는지 다음 세션 실측) |
> | 방문자 리뷰 | `POST pcmap-api.place.naver.com/graphql` (`visitorReviews` query) | 본문 · 평점 · 작성자 익명ID · 방문 카테고리 키워드 · 이미지 · 작성일 |
> | 병원 정보 탭 | `POST pcmap-api.place.naver.com/graphql` (query 명 미확인 — 다음 세션 캡처) | **진료영역 리스트** · **대표 키워드** · **원장 이력**(SNS·방송·학회) · **편의시설**(예약·주차·화장실) · 결제수단 · SNS 링크(블로그·유튜브) |
>
> 카카오맵도 같은 패턴 (`place.map.kakao.com/main/v/{id}` · `comment/v/{id}`) — 다음 세션 캡처 필요.
>
> ⭐ **정보 탭이 후기 못지않게 가치 큼** — "진료영역" 은 그 병원의 *자칭 시그널* 그 자체(리스트 형태로 깔끔, 본문 파싱보다 정확), "대표 키워드" 는 그 병원이 의도한 SEO 키워드, "원장 이력" 은 9영역 ③ 의료진 데이터 직격, "편의시설" 은 9영역 ⑤ 위치·접근 직격. visitorReviews 와 같은 GraphQL 엔드포인트로 한 요청에 묶일 수 있는지 캡처·실측 필요.
>
> **본 서비스 정의상 후기 시그널 + 정보 탭은 가장 중요한 외부 데이터.** 단 본격 구현 전 다음 결정 필요:
>
> 1. 토큰 발급(`ncpt.naver.com`)이 필수인지 — 비로그인·토큰 없이 graphql 호출 가능한지 실측
> 2. 정보 탭의 GraphQL query 명 캡처 + visitorReviews 와 한 요청에 묶을 수 있는지 시도
> 3. 이용약관·robots.txt 검토 — 자동화 수집 금지 조항 강도
> 4. 의료법 §56③ 룰은 그대로 유효 — 후기 본문 raw 는 **DDB 저장 + 임베딩·AI 자연어 설명 생성 입력으로만 사용**, 화면 노출은 키워드 빈도만 (사용자 직접 확인). 정보 탭의 "진료영역"·"대표 키워드"·"원장 이력" 은 사실 정보라 화면 노출 허용
> 5. 개인정보 — 응답에 `loginIdno`/`userIdno`/`nickname` 들어옴. **비로그인 호출 시 본인 ID 안 들어옴** (사용자 로그인 상태에서 캡처해서 그렇게 보였음). 그래도 닉네임·작성자 ID 는 마스킹 + raw 미저장 권장
> 6. 표본 범위 — 1만 풀스케일 vs 시연 10개 한정 (운영 안정성·토큰 깨짐 위험 가늠)
>
> 다음 세션 1순위 의제: 위 5개 실측·결정 → 본 박스 권고안으로 갱신 → `naver_place_crawler`·`kakao_crawler` 항목 구현 방향 확정. 본 박스가 풀릴 때까지 두 항목은 보류.
>
> ---
>
> **2026-05-28 실측 raw 노트** (결정은 미확정 — raw 사실만 박음)
>
> 환경: EC2 IP `13.223.112.152`. 1차로 httpx 단독으로 7회 호출 시도(차단), 2차로 Playwright Chromium headless 로 실제 브라우저 흐름 재현(성공). 사용자 브라우저 캡처 1건 보조 자료(질의 `"병원"` → place_id `37564839` 더서울치과 → `getVisitorReviews` 본문 정상 반환).
>
> **사실 1 — robots.txt**: `map.naver.com` · `m.map.naver.com` · `m.place.naver.com` · `map.kakao.com` · `place.map.kakao.com` 모두 `User-agent: * Disallow: /` (단 `map.naver.com` 만 `Allow: /$` `Allow: /p/$` 두 경로). 사용자 제안 모바일 진입점 `m.map.naver.com/search/interest-spot?type=HOSPITAL` 도 동일 robots Disallow.
>
> **사실 2 — 약관**: 네이버 이용약관 "**자동화된 수단(매크로·로봇·스파이더·스크래퍼) 을 이용하여 ... 네이버 검색 서비스에서 특정 질의어로 검색하거나 ... 일체의 행위를 시도해서는 안 됩니다.**" 카카오 약관 "회사가 정하지 않은 비정상적인 방법으로 시스템에 접근하는 행위" 금지.
>
> **사실 3 — ncpt 토큰 발급 흐름 (Playwright 가 자동 실행)**: 검색 페이지 진입 시 SDK 가 `GET ncpt.naver.com/static/ncaptcha-api.js?ncaptcha-sitekey={140자}` 로딩 → `POST ncpt.naver.com/v2/tokens?q={ts}&tid={11자}` body=`{"cipherText":"<클라이언트 환경 시그너처 암호화 blob, 600+ 자>"}` → 응답 `{"tokenId":"<base64 hash 76자>"}`. SDK 가 이걸 추가 가공해 검색 URL 의 `token=` 파라미터에 44자 짧은 토큰을 박음(예: `3QqL8xOOMxlWs08QlEUOozA8E5OwxlfLGOLvtskiT60=`). **httpx 단독으로 cipherText 만들 수 없어서 long token(629자, 패딩 없음) 만 받고 `CE_BAD_REQUEST` 차단됨** — 1차 실패의 원인.
>
> **사실 4 — search-history delta warmup**: `GET map.naver.com/p/api/kvfarm/search-history/delta` 는 로그인 필수 API (`XE401`). 비로그인 도 검색 정상 동작하므로 warmup 은 필수 아님. 사용자 캡처에 보였던 건 본인 로그인 상태였기 때문.
>
> **사실 5 — 검색 (Playwright)**: `GET map.naver.com/p/api/search/allSearch?query=...&token={44자}&sscode=svc.mapv5.search` HTTP 200 + `pageId=<UUID>`, `rcode=09140103` (서울 강남구 region code), `result.place.list[0].id` 에 place_id 박혀있음. 응답에 `ip: 13.223.112.152` (EC2 IP 그대로) — **EC2 IP 자체가 차단 리스트에 박혀있지 않음**.
>
> **사실 6 — GraphQL 실측 (`POST pcmap-api.place.naver.com/graphql`)**: Playwright context (쿠키·토큰 자동 박힘 상태) 안에서 `page.evaluate fetch credentials:include` 로 호출 → 정상 응답. `getVisitorReviews` query (size=3, businessType="hospital") 응답 본문에 후기 본문 raw + 평점 + 작성자 익명 ID 다 박혀 옴.
>
> **사실 7 — 5건 표본 안정성 (Playwright)**: 성공 3건, 실패 2건 (실패 둘 다 검색 결과에 place 없음 — 차단 아니라 매칭 실패). 1건당 약 18~25초 소요 (headless Chromium 부팅·SDK 토큰 발급·검색·상세 진입·GraphQL fetch 누적):
>
> | 쿼리 | place_id | 검색결과 reviewCount | graphql total_reviews | avgRating | authorCount |
> |---|---|---|---|---|---|
> | 자생한방병원 강남 | `19516906` | 1886 | 526 | 4.05 | 113 |
> | 더서울병원 성북 | `778531046` | 3416 | 356 | 4.02 | 64 |
> | 위담한방병원 강남 | `1520927430` | 2506 | 1002 | 4.24 | 228 |
> | 에이솝병원 강남 | place 없음(검색 매칭 실패) | — | — | — | — |
> | 예이진한의원 강남 | place 없음(검색 매칭 실패) | — | — | — | — |
>
> 검색결과 `reviewCount` vs graphql `total_reviews` 가 다른 이유는 검색결과는 "전체 리뷰(블로그·플레이스 합산)" 이고 graphql 은 "방문자 리뷰만" 카운트.
>
> **사실 8 — GraphQL 응답 스키마 (실측)**: `visitorReviews.items[]` 에 `body`(후기 본문 raw, 최대 수백 자), `rating`(병원 카테고리는 전부 null — 별점 미수집 카테고리), `visitedDate`, `visitCount`, `userIdno`(작성자 익명 5자 ID 예: `1f5LD`·`25hpK`·`2WoTG`), `loginIdno=""` (비로그인 호출이라 빈 값), `author.nickname`(서버 측 마스킹 — `su****` · `까뀽2` · `ymn****` 형태로 일부만 노출), `votedKeywords[].name`. `visitorReviewStats` 에 `review.avgRating`·`totalCount`·`authorCount`·`imageReviewCount`·`visitorReviewsTotal`·`ratingReviewsTotal`, `analysis.themes`·`menus`·`votedKeyword.details`. **단 실측 4건(자생한방·더서울·위담·사용자 캡처 619469917) 모두 `items[].themes=[]`·`items[].votedKeywords=[]`·`stats.analysis.themes=[]`·`stats.analysis.menus=[]`·`stats.analysis.votedKeyword.details` 빈 배열·`stats.analysis.votedKeyword.totalCount=null`**. 사용자 캡처 query 형식 그대로(`cidList:["223175","223176","223192","228995"]` + `includeContent:true`) 박아 봐도 동일. 즉 **네이버가 병원 카테고리에는 키워드 빈도·테마 통계를 노출하지 않음** (음식점·미용 등 다른 카테고리만 채워주는 듯). 사용자 캡처의 schema 정의에 votedKeyword 가 있는 건 query 가 범용이라 그렇고, 실 데이터는 빈 값. 후기 본문 raw 만 활용 가능, 집계 키워드는 우리 측에서 자체 추출(LLM·임베딩) 필요.
>
> **사실 9 — 개인정보 raw 노출**: 비로그인 호출 시 `loginIdno` 비어있음. `userIdno` 는 작성자 익명 5자 base32-ish ID (네이버 내부 식별자). `author.nickname` 은 서버 측에서 일부 마스킹 — 한글 닉네임은 그대로(`까뀽2`·`금본위`), 영문/숫자 닉네임은 처음 2~3자 + `****` (`su****`·`ymn****`). 즉 우리가 마스킹 추가 처리 안 해도 raw 응답이 이미 일부 마스킹 상태.
>
> **사실 10 — 카카오**: 공식 `dapi.kakao.com/v2/local/search/keyword.json` 키 없이 401 (`AccessDeniedError`, "Authorization : KakaoAK header" 필요) — 정상. 비공식 `place.map.kakao.com/main/v/{id}` 는 임의 ID(`8136181`·`17822251`) 시도 시 404. 카카오 실 place_id 형식·동일 ncpt-style 차단 구조 여부는 미실측.
>
> **사실 11 — Vision 입력 (박스 2 raw)**: `s3://kmuproj-10-clinic-focus-crawl/crawl/` 의 강남 502개 중 10개 무작위 표집 분석. 이미지 총 **300장(모든 사이트가 정확히 30장 cap)**, URL 패턴 잡음 의심 **78장(26%)**, 시술 힌트 URL/alt 매칭 **35장(11%)**, alt 보유 **164장(54%)**. 사이트별 잡음률 0~100% 편차 — `gn.chihyu.co.kr` 0%, `aesophospital.com` 3%, `re-bom.com` 100%. `re-bom.com` 의 `menu_2_1_2_manualTherapy.png` (alt="도수치료") 는 URL `menu_` 패턴 때문에 잡음 분류됐으나 실제 시술 카테고리 그리드 — **URL 패턴 단독 잡음 룰은 거짓 양성 다발**, alt 텍스트가 결정적 시그널.
>
> **사실 12 — `getPhotoViewerItems` + `getPhotoTabFilters` (사용자 후속 캡처 기반 4건 실측)**: 네이버 사진 탭이 노출하는 photos[] 가 박스 1·2 양쪽에 시그널 추가. 표본:
>
> | 병원 | photos 총 | ibu(공식) | visitor(후기) | ugc(블로그) | unique blog 시드 |
> |---|---|---|---|---|---|
> | 자생한방 강남 | 46 | 3 | 4 | 39 | (미집계, 다음 세션) |
> | 더서울 성북 | 61 | 20 | 1 | 40 | 9 |
> | 위담 강남 | 60 | 20 | 0 | 40 | 7 |
> | 정릉아동보건지소(619469917) | 20 | 1 | 0 | 19 | 4 |
>
> 각 사진의 `photoType`:
> - `ibu` = 병원이 네이버 플레이스에 직접 올린 공식 사진 (= 자칭 시그널 raw, `businessName` 박힘)
> - `visitor` = 방문자 후기 사진 (`text` 에 후기 본문 일부)
> - `ugc` = 외부 블로그 사진. `externalLink.url` 에 `blog.naver.com/.../{postId}` 박혀 있음 (= **블로그 시그널 시드 URL 을 네이버가 큐레이션해서 줌** — `v1/search/blog` 검색보다 정확한 매칭)
>
> `getPhotoTabFilters` 의 `AI View.subTabFilters`: 자생한방 강남만 `(내부, INTERIOR)`·`(외부, EXTERIOR)` 두 카테고리 노출(나머지 3건은 AI View 탭 자체 없음). 사진 양·카테고리에 따라 노출. **네이버가 이미 사진을 자동 분류했음 = 박스 2 Vision 트랙에 직접 시그널 추가** (외부 시설/내부 시설/시술 결과 등).
>
> **실측 코드·query·응답 raw 저장**: [`ai/scratch/naver-place-probe-2026-05-28/`](../../ai/scratch/naver-place-probe-2026-05-28/) (README + probe_search·probe_reviews·probe_photos 실행 스크립트 + queries/*.graphql 4개 + samples/*.json 9개). 다음 세션이 코드 디테일 재현 시 이 폴더만 보면 됨.
>
> **운영 비용·제약 추가 메모 (수치 raw)**:
> - **EC2 부담**: 1건당 headless Chromium 18~25초. 1만 풀커버 시 단일 EC2 직렬 처리 = ~50~70시간. 병렬화·헤드리스 풀 운영 필요
> - **Playwright Chromium 시스템 의존성** (현 EC2 에 설치 완료): `atk at-spi2-atk nss cups-libs libdrm libXcomposite libXdamage libXrandr libXfixes libXScrnSaver libxkbcommon mesa-libgbm pango cairo alsa-lib`
> - **검색 매칭 실패율** = 표본 2/5 (40%) — 정확한 병원명 + 지역 조합으로 검색해야 후보 1번이 정확. HIRA `yadmNm` 그대로 박았을 때의 매칭률은 별도 실측 필요
> - **EC2 IP 차단 위험**: 1차 7회 호출에서도 차단 표시 없음(응답에 우리 IP 노출), 5건 패키지도 안정. 단 1만 풀커버 시 IP rate-limit 발생 가능성은 미실측
>
> **미해명 항목** (다음 세션):
> - ~~GraphQL `votedKeyword.details` · `themes` 비어있는 이유~~ → 사실 8 갱신: 병원 카테고리는 노출 안 함이 확정. 우리 측에서 후기 본문 raw 로 직접 키워드 추출해야 함
> - 정보 탭 (`진료영역` · `대표 키워드` · `원장 이력` · `편의시설`) query 명 — visitor 탭 외 다른 탭(`/home`·`/information`) 진입 시 호출되는 GraphQL 캡처 필요
> - ~~카카오 비공식 엔드포인트의 실제 구조 (place_id 형식·ncpt-style 차단 여부)~~ → 아래 카카오 raw 노트(사실 13~24) 로 해소
> - 1만 풀커버 시 EC2 IP rate-limit (직렬 50~70시간 부담 + 병렬화 시 IP 차단 임계 미실측. 네이버·카카오 양쪽 동일하게 미실측)
>
> ---
>
> **2026-05-28 실측 raw 노트 — 카카오맵** (사용자 캡처 4 endpoint + EC2 실측. 결정은 미확정, raw 사실만 박음)
>
> 환경: EC2 IP `13.223.112.152` 동일. 4 endpoint 모두 httpx 단발 호출(Playwright 미사용). 사용자 캡처: 검색 `searchJson` + 상세 `panel3/8094954` + 후기 `tab/reviews/kakaomap/8094954` + 블로그 `tab/reviews/blog/8094954?page=1`.
>
> **사실 13 — robots.txt + 약관 (네이버 사실 1·2 동일)**: `map.kakao.com` · `place.map.kakao.com` 모두 자동화 금지. 카카오 약관 "회사가 정하지 않은 비정상적인 방법으로 시스템에 접근하는 행위" 금지 — 자동화 수집은 약관 위반 소지.
>
> **사실 14 — 호출 단순성 (vs 네이버)**: 4 endpoint 모두 **ncpt 토큰 발급·Playwright Chromium 부팅 불필요**. httpx 단발 + 헤더 셋(`User-Agent` PC + `Referer` + `Accept: application/json` + `pf: web`)만 맞으면 200. 헤더 누락 시 `406 Not Acceptable`(`place-api.map.kakao.com`) 또는 `302 → www.kakao.com/500.ko.html`(`m.map.kakao.com`). 네이버 흐름의 토큰 발급 비용 0.
>
> **사실 15 — 검색 (`m.map.kakao.com/actions/searchJson`)**: `type=PLACE&q={쿼리}&pageNo=1` 단발. PC UA + `Referer: https://m.map.kakao.com/actions/searchView` + `X-Requested-With: XMLHttpRequest` 박으면 200 (41KB). 사용자 캡처의 `wxEnc/wyEnc` 좌표 enc·`cidx`·`rcode`·`busStopCount`·`placeCount` 는 **선택 파라미터** — 없어도 동작. 응답 `placeList[].confirmid` 가 place_id, `cate_name_depth2: "병원"` 필터로 의료기관 한정.
>
> **사실 16 — 5건 표본 매칭률 (네이버와 동일 패턴)**: 5건 중 3건 성공, 2건 실패 (`에이솝병원 강남`·`예이진한의원 강남` — 차단 아니라 매칭 실패). 매칭률 카카오 = 네이버 = 3/5. 1건당 1~3초 (네이버 18~25초 vs).
>
> | 쿼리 | place_id | 검색 reviewCount | reviews 응답 | blog review_count | photos.counts.total |
> |---|---|---|---|---|---|
> | 자생한방병원 강남 | `27388604` | 324 | 303 | 324 | 704 |
> | 더서울병원 성북 | `202729757` | 1096 | 73 | 1096 | (별도) |
> | 위담한방병원 강남 | `544191051` | 765 | 86 | 765 | (별도) |
> | 에이솝병원 강남 | place 없음 | — | — | — | — |
> | 예이진한의원 강남 | place 없음 | — | — | — | — |
>
> **사실 17 — `panel3` 한 호출의 풍부함**: `GET https://place-api.map.kakao.com/places/panel3/{place_id}` 단발에 다음을 묶어서 줌:
> - `summary` — 이름·주소·전화·홈페이지·결제수단·meta
> - `place_add_info.tags[]` — **자칭/카테고리 정제 키워드 raw** (자생한방 18개: `2차병원·관절염·근육통·도수치료·무릎관절치료·물리치료·비염·생리통클리닉·신경클리닉·실손24·안면신경마비·오십견·자동차보험진료기관·추나요법·턱관절질환·통증치료·한방클리닉·회전근개손상`). `primary_focus` 시드 직접 사용 가능
> - `medical.hira` — HIRA 공공 데이터 정제본 (`medical_center_type`·`specialized_field`·`doctor_count{total,general,intern,resident,specialist}`·`subjects[]`·`established_at`·`open_infos[]`)
> - `medical.emergency_center` — 응급의료 메타
> - `photos.counts` — `{total, mystore, vendor, vod, kakaomap_review, food, indoor, outdoor, menu}` 자체 사진 분류
> - `visitor.{day_of_week, max_uv, monday_uv[24], ..., sunday_uv[24], labels[0..23]}` — 시간대별/요일별 방문자 UV (`-1` = 데이터 없음)
> - `blog_review.{review_count, reviews[]}` — 블로그 1페이지 내장
> - `kakaomap_review.{score_set, strength_description, reviews[], has_next}` — 후기 1페이지 내장 (단 더서울 케이스는 null — 노출 조건 미실측)
> - `open_hours.{all, headline, week_from_today}` — 영업시간
> - `panel_card_tags[]` / `panel_tab_tags[]` — UI 표시 키 (`TITLE/PHOTO/BIZ/NEWS/AI_MATE/SUMMARY/INFO/EVENT_KEYWORD/PRODUCT/AI_QUESTION/BOOKING/SPECIAL/VISITOR/REVIEW/RANKING/BLOG`)
> - `my_store_notice.{notice_count, notices, mystore_intro, main_photo_url}` — 사업자 본인 박은 자기소개·공지 (자칭 시그널 핵심. 더서울·위담만 노출. 노출 조건 미실측)
> - `ai_content_warning.{is_home_tab_display_enabled, is_info_tab_display_enabled}` — 카카오가 "AI 콘텐츠 경고" UI 가시성을 boolean 으로 노출 (의료법 회색지대 인지)
>
> **즉 panel3 1회 = 네이버 visitorReviews + getPhotoViewerItems + 정보 탭 3 호출에 해당**. 1만 풀커버 시 호출 비용 ⅓ 절약.
>
> **사실 18 — 후기 (`tab/reviews/kakaomap/{id}`)**: `score_set.{review_count, average_score, strength_counts}` + `strength_description[].{id, name, icon_url}` + `reviews[].{review_id, contents, star_rating, photo_count, photos[], strength_ids[], registered_at, updated_at, status, meta}` + `has_next` + `timeline_score_table`. 핵심:
> - **`strength_description` 라벨이 4종 고정** (`13:가격, 10:전문성, 2:친절, 4:주차`) — 4건 표본 모두 동일 매핑. 카테고리 무관. 네이버는 카테고리별 분기인데 (병원은 빈 배열) 카카오는 좁은 고정 셋
> - **`star_rating` 0~5 정수 노출** — 네이버 병원 카테고리 `rating=null` 과 다름
> - 본문 평균 61~288자, 최대 1972자
> - 1 호출 11~20건 반환. `?page=2` 박아도 같은 items — **페이지네이션 키 미실측** (cursor/offset 후보)
> - `only_photo_review=true` 필터 = 사진 후기만 (Vision 시드 노이즈 감소)
> - `reviews[].photos[].kakaomap_review_photo_meta.owner.{map_user_id, nickname, image_url}` = **마스킹 없이 raw** (네이버는 서버 측에서 `su****` 마스킹). 저장 정책 결정 필요
>
> **사실 19 — 블로그 (`tab/reviews/blog/{id}?page=N`)**: `review_count` + `reviews[].{review_id, confirm_id, title, contents, origin_url, author, photo_count, photos[], registered_at}`. 핵심:
> - **`origin_url` 100% `blog.naver.com`** — 4건 표본 40 URL 전부. 카카오가 네이버 블로그를 자체 큐레이션
> - 네이버 `getPhotoViewerItems.ugc.externalLink.url` 과 **같은 시드 풀, 다른 큐레이션 시그널**: 카카오 blog tab = 텍스트 본문 위주, 네이버 photo ugc = 사진 첨부 위주. **두 채널 합집합 = BlogSignal 시드 가장 풍부한 회수**
> - `contents` 발췌 본문 (수백 자 raw) — 블로그 원문 추가 fetch 없이도 키워드 빈도 가능
> - `?page=N` 동작 확인 (reviews 와 달리 페이지네이션 정상)
> - 위담 케이스 `contents` 첫 문장: "본 게시글은 의료법 제 56조 1항을 준수하여 작성되었습니다." = **광고성 블로그 표시 마커**. 광고/실후기 분리 룰 토큰 후보
> - `author` raw 닉네임 — 마스킹 없이 노출 (작성자 본인 노출 의도)
>
> **사실 20 — `panel3.place_add_info.tags` 와 분류 스키마**: 자생한방 18개 태그 중 `2차병원·관절염·근육통·도수치료·물리치료·비염·통증치료·한방클리닉·추나요법` 은 `standard_specialty='한의원'`·`primary_focus=['추나·도수','침구']` 와 정렬됨. `자동차보험진료기관·실손24` 는 보험 청구 정책 시그널 (자칭 마케팅 키워드). 카카오 태그 풀이 우리 `primary_focus` 22 후보군 예시 (`ai/CLAUDE.md` 분류 스키마 섹션) 와 매핑 가능. **즉 룰 기반 분류기의 자칭 추출 입력으로 panel3.tags 가 자체 사이트 텍스트보다 정제도 높음**.
>
> **사실 21 — `panel3.medical.hira` 와 HIRA 직접 호출 비교**: 카카오 정제본은 `doctor_count` 세분화·`specialized_field`·`established_at` 노출. 단 HIRA 공공 API 의 `ykiho`·정확한 진료과목 코드·요양기관번호는 카카오에 없음. **HIRA 직접 호출 흐름은 유지, 카카오 정제본은 보조 시그널**. 충돌 시 HIRA 우선.
>
> **사실 22 — 개인정보 raw 노출 (네이버 사실 9 비교)**: `reviews[].photos[].kakaomap_review_photo_meta.owner.map_user_id` (9~10자리 숫자 ID) + `nickname` (작성자 닉네임 원문) + `image_url` (카카오톡 프로필 사진 URL) **마스킹 없이 원본**. 네이버는 서버 측 마스킹(`su****`) 후 노출. 카카오 raw 저장 시 우리 측 마스킹 의무 발생 — `kakao_place_adapter._mask_review_item` 가 화이트리스트 방식으로 owner 통째 제거. `loginIdno`·session 정보는 비로그인 호출이라 없음. (실측 raw 의 owner·author 식별자는 repo 커밋 전 redact 처리됨 — `samples/*.json` 의 `owner`/`author` 는 placeholder)
>
> **사실 23 — `m.map.kakao.com/actions/searchJson` 모바일 UA 차단**: 모바일 UA 또는 Referer 누락 시 `302 → https://www.kakao.com/500.ko.html` 500 페이지로 리다이렉트. PC UA + `Referer: https://m.map.kakao.com/actions/searchView` 박으면 200. 즉 카카오는 진입점 봇 차단을 검색 엔드포인트 한 군데에 집중, `place-api.*` 는 헤더만 맞으면 통과. **검색은 단순 헤더 위장, 상세 4 endpoint 는 헤더 셋 외 추가 차단 없음**.
>
> **사실 24 — 실측 코드·query·응답 raw 저장**: [`ai/scratch/kakao-place-probe-2026-05-28/`](../../ai/scratch/kakao-place-probe-2026-05-28/) (README + probe_search·probe_panel3·probe_reviews·probe_blog 실행 스크립트 + queries/*.http 4개 + samples/*.json 13개). 다음 세션이 코드 디테일 재현 시 이 폴더만 보면 됨.
>
> **운영 비용·제약 추가 메모 (수치 raw)**:
> - **EC2 부담**: 1건당 httpx 1~3초 (네이버 18~25초 vs ⅛). 1만 풀커버 시 단일 EC2 직렬 ≈ 3~8시간. Playwright 시스템 의존성 없음
> - **호출 수**: panel3 1회로 네이버 3 호출분 회수 → **풀커버 호출 비용 카카오 = 1회/병원 vs 네이버 = 3 호출/병원**
> - **검색 매칭 실패율** = 2/5 (40%, 네이버와 동일) — 정확한 병원명 + 지역 조합 필요. HIRA `yadmNm` 매칭률 미실측
> - **EC2 IP rate-limit**: 4 endpoint 표본 16회 호출 안정. 1만 풀커버 시 임계 미실측 (네이버와 동일하게 IP 풀·딜레이·재시도 정책 필요)
>
> **카카오 미해명 항목** (다음 세션):
> - `reviews` 페이지네이션 키 — `?page=N` 무시. cursor/offset/sort 후보 미실측
> - `panel3.kakaomap_review` 가 더서울 케이스에만 `null` 인 조건 (해당 병원은 reviews 호출 시 73건 노출되는데 panel3 안엔 없음)
> - `panel3.my_store_notice.mystore_intro` 노출 조건 (더서울·위담만 노출, 자생한방·춘원당 미노출)
> - 카카오 자체 광고/실후기 분리 룰 — 블로그 본문 첫 문장 "의료법 제 56조 1항" 마커 빈도
> - 1만 풀커버 시 IP rate-limit 임계 (네이버와 공통 미해명)

> ✅ **결정됨 (2026-05-28, 사용자) — Vision 입력 = 병원 자체 사이트 한정**
>
> Vision 분석 입력은 **병원 자체 사이트 이미지(옵션 A/D)만** 쓴다. 네이버·카카오 크롤링으로 얻은 이미지는 **Vision 분석 입력에서 제외**. 이유: Vision 시그널(30%)은 "병원이 자기 사이트에서 무엇을 시각적으로 내세우는가"가 핵심이라 외부 플랫폼 큐레이션 사진이 섞이면 자칭 시그널이 오염됨.
>
> **단 네이버·카카오 사진은 FE 대표 이미지 용도로는 활용**. 공식 API(네이버 `v1/search/local`·카카오 `dapi.kakao.com/keyword`) 응답에 **이미지 URL 필드가 아예 없음**(2026-05-28 실측 확인) → FE 가 검색 결과·상세에 쓸 병원 대표 이미지는 크롤링 사진(카카오 `my_store_notice.main_photo_url` 우선 → `panel3.photos[].url` 폴백)에서만 회수 가능. 이건 Vision 분석이 아니라 **이미지 URL/S3 저장**만 하는 별개 경로. 아래 옵션 E·F 는 그래서 **Vision 입력이 아니라 FE 대표 이미지 시드**로 재분류됨.
>
> ---
>
> 현재 BE 의 `crawl_data.json` `images[]` 필드는 **사이트 HTML `<img>` 태그 URL 메타만** 담음 (`url`·`page_url`·`alt_text` 3 필드). 이미지 바이트 다운로드·Vision 분석은 Phase C AI 책임. 단 다음 사실로 입력 전략 재검토 필요:
>
> - **한국 의원 사이트는 이미지 비중이 매우 큼** — 풀스크린 슬라이드·시술 전후 사진·시술 카테고리 그리드 등. 텍스트 적고 이미지로 정체성 표현하는 경향
> - `<img>` 태그만 긁으면 **CSS `background-image`·`<picture>`·SPA lazy-load 이미지 누락**. 시술·기기 사진이 누락되면 Vision 시그널(30%) 가치 ↓
> - 표본 1건(`weedahm.com`) 30개 이미지 중 로고·아이콘·캘린더 같은 잡음 다수 — 잡음 비율 실측 안 됨
>
> 4 입력 옵션:
>
> | 옵션 | 입력 | 장점 | 단점 |
> |---|---|---|---|
> | A. `<img>` URL 다운로드 (현재 가정) | 사이트의 `<img>` URL → 바이트 받아 Vision | URL 이미 수집됨. 추가 작업 작음 | 로고·아이콘 잡음. CSS background 시술 사진 누락. SPA 정적 HTML 누락 |
> | B. 사이트 전체 스크린샷 (Playwright `full_page=True`) | 풀페이지 캡처 1장 | 사용자에게 실제 보이는 화면. 레이아웃·문구·배너 다 포함. SPA 대응 | 1장 1~5MB. Vision 토큰 폭증. 페이지 너무 길면 토큰 한도 초과 |
> | C. 페이지 N구간 분할 스크린샷 | 풀페이지를 스크롤 구간별 캡처 | B 토큰 부담 완화. 영역별 분석 가능 | 구현 복잡. 구간 매핑 관리 |
> | D. `<img>` + `background-image` + Playwright `getComputedStyle` | DOM 에서 보이는 모든 이미지 | A 누락 완화. CSS 배경 시술 사진 회수 | 정제 필요. 구현 중간 난이도 |
>
> 결정 필요:
>
> 1. 표본 5~10개 사이트로 A 결과 잡음 비율·시술 사진 누락률 실측
> 2. A 누락이 많으면 D 시도. 그래도 부족하면 B/C
> 3. `MAX_VISION_IMAGES=10` 제약 안에서 어떤 입력이 최대 정보량인지 가늠
> 4. BE 가 입력 형식을 바꾸면 `crawl_data.json` `images[]` 스키마 변경 — shared/models.py `CrawledImage` 영향
>
> 다음 세션 2순위 의제: 표본 실측 → 옵션 선택 → BE 이미지 수집 방식 갱신 + AI `analyze_images` 입력 시그니처 확정. 이 박스도 풀릴 때까지 Phase C Vision 본체(`ai/pipeline/vision.py`) 진입 보류.
>
> ---
>
> **2026-05-28 실측 raw 노트** (위 후기 시그널 전략 박스의 "사실 9" 참조). 10개 표본 분석으로 잡음·시술 사진 hit률·alt 보유율 raw 수치는 박음. 결정 1~4 의 옵션 채택 여부(A vs D vs B/C) 는 미확정.
>
> **FE 대표 이미지 시드 (2026-05-28 — Vision 입력 아님, 위 결정 박스 참조)**:
>
> 아래는 Vision 분석이 아니라 **FE 가 쓸 병원 대표 이미지 URL 회수 경로**. Vision 입력은 자체 사이트(A/D)로 동결됨.
>
> | 시드 | 출처 | 비고 |
> |---|---|---|
> | E. 네이버 photoViewer ibu 사진 | 네이버가 노출하는 병원 공식 사진 (`photoType="ibu"`, `businessName` 박힘) | ibu = 병원이 직접 올린 공식 사진. ugc/visitor 는 외부·후기라 대표 이미지 부적합 |
> | F. 카카오 `my_store_notice.main_photo_url` → `panel3.photos[].url` | 사업자 본인 설정 대표 사진 우선, 없으면 사진 배열 폴백 | main_photo_url = mystore 등록 병원만(더서울·위담 O, 자생·춘원당 X). 폴백 `photos[]` 는 후기 사진이라 owner PII 메타 제거 후 URL 만 |
>
> 본체 흐름: 카카오 `parse_place` 가 `representative_image_url` 1개를 뽑아 DDB `KAKAO#PLACE` 에 저장 → BE `/api/hospitals/{id}` 응답·검색 카드에 노출. S3 미러는 핫링크 깨짐 대비 추후 (URL 저장만으로 PoC 충분). **개인정보**: 폴백 사진의 `kakaomap_review_photo_meta.owner` 는 저장 안 함 (URL 만).
