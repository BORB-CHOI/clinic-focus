# 카카오맵 비공식 API probe — 2026-05-28

다음 세션이 디테일을 잃지 않도록 실측 코드·endpoint 명세·응답 구조 샘플을 한 폴더에 남김.
배경·결정은 [`docs/plans/task-queue.md`](../../../docs/plans/task-queue.md) "Phase B 후기 시그널 전략" 박스의 **2026-05-28 실측 raw 노트 (카카오)** 참조.

## 핵심 한 줄

EC2 + httpx 단발 호출(4 endpoint 모두)로 검색·상세·후기·블로그 raw JSON 회수 가능. 네이버처럼 ncpt 토큰 발급·Playwright 부팅 **불필요**. 헤더 셋(Referer + UA + Accept + `pf: web`)만 맞으면 200. 단 robots.txt + 약관 자동화 금지.

## 폴더 구조

```
kakao-place-probe-2026-05-28/
├── README.md                        이 파일
├── probe_search.py                  검색 → place_id (5건 동일 표본)
├── probe_panel3.py                  상세 홈 (4 place_id)
├── probe_reviews.py                 후기 (4 place_id)
├── probe_blog.py                    블로그 (4 place_id)
├── queries/
│   ├── 01_search.http               m.map.kakao.com/actions/searchJson
│   ├── 02_panel3.http               place-api .../places/panel3/{id}
│   ├── 03_reviews.http              place-api .../places/tab/reviews/kakaomap/{id}
│   └── 04_blog.http                 place-api .../places/tab/reviews/blog/{id}?page=N
└── samples/                         응답 raw JSON 샘플 (place_id 별)
    ├── search_*.json                3건 성공
    ├── panel3_*.json                4건 성공
    ├── reviews_*.json               4건 성공
    └── blog_*_p1.json               4건 성공
```

## 실행

```bash
cd /home/ec2-user/clinic-focus
.venv/bin/python ai/scratch/kakao-place-probe-2026-05-28/probe_search.py
.venv/bin/python ai/scratch/kakao-place-probe-2026-05-28/probe_panel3.py
.venv/bin/python ai/scratch/kakao-place-probe-2026-05-28/probe_reviews.py
.venv/bin/python ai/scratch/kakao-place-probe-2026-05-28/probe_blog.py
```

## 4건 표본 (이미 실측됨)

| place_id | 이름 | 검색결과 reviewCount | reviews 응답 review_count | blog review_count | photos.counts.total |
|---|---|---|---|---|---|
| `8094954`   | 춘원당한의원 (사용자 캡처) | (검색 미수행) | 11   | 60   | (panel3 별도) |
| `27388604`  | 자생한방병원 강남          | 324  | 303  | 324  | 704 |
| `202729757` | 더서울병원 성북            | 1096 | 73   | 1096 | (panel3 별도) |
| `544191051` | 위담한방병원 강남          | 765  | 86   | 765  | (panel3 별도) |

## 5건 패키지 검색 매칭

3/5 성공, 2/5 실패 (`에이솝병원 강남`·`예이진한의원 강남`) — **네이버 실측과 정확히 같은 패턴** (차단 아닌 검색어 매칭 실패).

## 호출 흐름 한눈에

```
[검색]    m.map.kakao.com/actions/searchJson?type=PLACE&q={쿼리}
            → placeList[0].confirmid = place_id
              + cate_name_depth2="병원"·reviewCount·tel·roadview
            (1회 HTTP. PC UA + Referer + X-Requested-With 필수)

[상세]    place-api.map.kakao.com/places/panel3/{place_id}
            → summary + place_add_info.tags + medical.hira + photos.counts + visitor.uv
              + blog_review.reviews[] (1페이지 내장) + kakaomap_review.reviews[] (1페이지 내장)
            (1회 HTTP. Referer + Origin + pf=web 필수)

[후기]    /places/tab/reviews/kakaomap/{place_id}?order=RECOMMENDED&only_photo_review=false
            → score_set + strength_description + reviews[]
            (panel3 의 kakaomap_review 와 동일 구조. 후속 페이지·정렬·필터 옵션 사용 시 호출)

[블로그]  /places/tab/reviews/blog/{place_id}?page=N
            → reviews[]: title, contents (발췌), origin_url (blog.naver.com), author
            (panel3 의 blog_review 와 동일 구조. 후속 페이지)
```

**panel3 가 한 번 호출에 정보·후기 1페이지·블로그 1페이지·사진 카운트·visitor UV·HIRA 정제본을 다 묶어줌**. 1만 풀커버 시 호출 비용 ⅓ 절약 (네이버 후기·사진·정보 3 호출 분리 대비).

## 응답 핵심 시그널

### `panel3.place_add_info.tags` — primary_focus 시드

`["2차병원", "관절염", "근육통", "도수치료", "무릎관절치료", "물리치료", "비염", "생리통클리닉", "신경클리닉", "실손24", "안면신경마비", "오십견", "자동차보험진료기관", "추나요법", "턱관절질환", "통증치료", "한방클리닉", "회전근개손상"]`

자생한방 18개 태그. 카카오가 이미 자칭/카테고리 키워드를 추출해서 박아둠. 우리 룰 기반 분류기의 직접 입력 후보. shared/models 의 `primary_focus` 시드로 그대로 사용 가능.

### `panel3.medical.hira` — HIRA 공공 데이터 정제본

```json
{
  "medical_center_type": "한방병원",
  "specialized_field": "한방척추질환",
  "doctor_count": {"total": 72, "general": 4, "intern": 8, "resident": 31, "specialist": 29},
  "subjects": [...],
  "open_infos": [...],
  "established_at": "1999-06-21"
}
```

우리가 별도 HIRA 호출하던 흐름 (BE 트랙) 부분 대체 가능. 단 HIRA `ykiho`·정확한 진료과목 코드는 공공 API 가 우위 — 카카오 정제본은 보조 시그널.

### `panel3.photos.counts` — 사진 자체 분류

`{total: 704, mystore: 0, vendor: 0, vod: 1, kakaomap_review: 87, food: 0, indoor: 206, outdoor: 32, menu: 0}`

카카오가 이미 indoor/outdoor/menu/kakaomap_review 분류. 박스 2 Vision 입력 옵션 E 후보 (네이버 `AI View.subTabFilters` 와 동급).

### `reviews.score_set` + `strength_description` — 후기 강점 집계

```json
"score_set": {
  "review_count": 303, "average_score": 4.6,
  "strength_counts": [{"id": 2, "count": 164}, {"id": 10, "count": 145}, {"id": 4, "count": 50}, {"id": 13, "count": 32}]
}
"strength_description": [
  {"id": 13, "name": "가격"},
  {"id": 10, "name": "전문성"},
  {"id":  2, "name": "친절"},
  {"id":  4, "name": "주차"}
]
```

**카테고리 무관 고정 4종 라벨**. 네이버는 병원 카테고리에 `votedKeyword` 빈 배열인데 카카오는 노출. 단 4종으로 좁아 primary_focus 추출엔 약하고 "general 평가" 시그널.

### `reviews.reviews[].contents` + `star_rating` — 본문·평점

네이버 병원 카테고리는 `rating=null` 인데 카카오는 `star_rating` 0~5 정수 노출. 본문 평균 61~288자, 최대 1972자.

### `blog.reviews[].origin_url` + `contents` — 블로그 시드 + 발췌

`origin_url` 100% `blog.naver.com` (4건 표본 40 URL). 네이버 `getPhotoViewerItems` ugc 와 같은 시드 풀이지만 다른 큐레이션 (텍스트 위주 vs 사진 위주). 두 채널 합집합 = BlogSignal 시드 가장 풍부한 회수 경로.

## 비교 — 네이버 vs 카카오

| 항목 | 네이버 | 카카오 |
|---|---|---|
| 차단·토큰 | ncpt SDK 필수, Playwright Chromium 부팅 18~25초 | httpx 단발 가능. 헤더만 셋 |
| 검색 매칭률 | 3/5 (5건 표본) | 3/5 (동일 5건 표본) |
| 정보·후기·사진 호출 | 3 분리 (GraphQL visitorReviews/Stats/photoViewer) | 1 통합 (panel3) + 후속 페이지만 분리 |
| 후기 키워드 집계 | 병원 카테고리에 빈 배열 (themes/votedKeyword 미노출) | strength 4종 고정 라벨 노출 |
| 후기 본문 raw | `items[].body` (수백 자, rating=null) | `reviews[].contents` (수백 자, star_rating 0~5) |
| 작성자 ID·닉네임 | `userIdno` 5자 + `author.nickname` 서버 마스킹 (`su****`) | `kakaomap_review_photo_meta.owner.{map_user_id, nickname, image_url}` 마스킹 없이 raw |
| 사진 자체 분류 | `getPhotoTabFilters.AI View.subTabFilters` (선택 노출) | `photos.counts` (항상 노출, indoor/outdoor/menu) |
| 블로그 시드 | `getPhotoViewerItems.ugc.externalLink.url` (사진 기반) | `tab/reviews/blog` (텍스트 기반). 둘 다 blog.naver.com 100% |
| 자칭 태그 | 없음 (정보 탭 query 미발견) | `place_add_info.tags[]` 정제 키워드 직접 노출 |
| HIRA 정제본 | 없음 | `medical.hira` (의사 수·진료과목·전문분야) |
| 방문자 UV 분포 | 없음 | `visitor.{day_of_week, max_uv, monday_uv[24], ...}` 시간대별 |
| 1만 풀커버 비용 | 1건 18~25초 × 1만 ≈ 50~70시간 | 1건 1~3초 × 1만 ≈ 3~8시간 (단 IP rate-limit 미실측) |

## 미해명 항목 (다음 세션)

- **reviews `?page=N` 페이지네이션** — `?page=2` 박아도 같은 items 반환. cursor/offset/sort 후보 키 미실측
- **EC2 IP rate-limit** — 1만 풀커버 시 카카오 차단 임계. 4건 표본은 안정 (네이버 5건 표본도 안정과 같음)
- **카카오 자체 광고 마커** — blog `contents` 첫 문장에 "본 게시글은 의료법 제 56조 1항을 준수하여 작성되었습니다." 같은 광고 표시. 광고/실후기 분리 룰 토큰 추출 필요
- **`reviews.photos[].kakaomap_review_photo_meta.owner` 개인정보** — 마스킹 없이 카카오톡 ID·닉네임·프로필 사진 URL raw. 저장 정책 결정 필요
- **`my_store_notice.mystore_intro`** — 사업자 본인이 박은 자기소개. 자칭 컨셉 시그널 핵심. 더서울·위담만 노출, 자생한방·춘원당 미노출. 노출 조건 미실측
