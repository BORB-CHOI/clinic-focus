# 네이버 플레이스 비공식 GraphQL probe — 2026-05-28

다음 세션이 디테일을 잃지 않도록 실측 코드·query 본문·응답 구조 샘플을 한 폴더에 남김.
배경·결정은 [`docs/plans/task-queue.md`](../../../docs/plans/task-queue.md) "Phase B 후기 시그널 전략" 박스의 **2026-05-28 실측 raw 노트** 참조.

## 핵심 한 줄

EC2 + Playwright Chromium headless 로 ncpt SDK 가 짧은 토큰(44자) 자동 발급 → `pcmap-api.place.naver.com/graphql` 직접 호출 → 후기 본문 raw + 사진 메타·블로그 외부 링크 수집 가능. 단 robots.txt + 약관 명시적 자동화 금지.

## 폴더 구조

```
naver-place-probe-2026-05-28/
├── README.md                       이 파일
├── probe_search.py                 검색 → place_id (5건 패키지)
├── probe_reviews.py                visitorReviews + Stats (4건 표본)
├── probe_photos.py                 photoViewer + Filters (4건 표본)
├── queries/
│   ├── visitor_reviews.graphql     getVisitorReviews query 본문 (사용자 캡처 그대로)
│   ├── visitor_review_stats.graphql
│   ├── photo_viewer_items.graphql  getPhotoViewerItems ($isNmap 빼는 버전)
│   └── photo_tab_filters.graphql
└── samples/                        응답 raw JSON 샘플 (place_id 별)
    ├── search_jaseng.json
    ├── reviews_jaseng.json
    └── photos_jaseng.json
```

## 실행

```bash
# 전제: Playwright Chromium + 시스템 lib 설치됨 (EC2 onboarding 시 한 번)
cd /home/ec2-user/clinic-focus
.venv/bin/python ai/scratch/naver-place-probe-2026-05-28/probe_search.py
.venv/bin/python ai/scratch/naver-place-probe-2026-05-28/probe_reviews.py
.venv/bin/python ai/scratch/naver-place-probe-2026-05-28/probe_photos.py
```

## 4건 표본 (이미 실측됨)

| place_id | 이름 | 검색결과 reviewCount | graphql total | avgRating | photos 총 (ibu/visitor/ugc) |
|---|---|---|---|---|---|
| `19516906` | 자생한방병원 강남 | 1886 | 526 | 4.05 | 46 (3/4/39) |
| `778531046` | 더서울병원 성북 | 3416 | 356 | 4.02 | 61 (20/1/40) |
| `1520927430` | 위담한방병원 강남 | 2506 | 1002 | 4.24 | 60 (20/0/40) |
| `619469917` | (소규모 — 정릉아동보건지소) | — | 2 | 0 | 20 (1/0/19) |

## 5건 패키지 검색 매칭

3/5 성공 — 실패 2건은 검색 매칭 실패(차단 X, 단순 "에이솝병원 강남"·"예이진한의원 강남" 명칭 매칭 안 됨).

## visitorReviews 응답 핵심 필드

```
items[] {
  body            # 후기 본문 raw (최대 수백 자)
  rating          # 병원 카테고리는 전부 null
  visitedDate     # "2026.05.22."
  visitCount      # 방문 횟수
  userIdno        # 작성자 익명 5자 ID (예: 1f5LD, 25hpK)
  loginIdno       # 비로그인 호출 시 ""
  author.nickname # 서버측 일부 마스킹 (su****·까뀽2·ymn****)
  themes          # [] (병원 카테고리는 모두 빈 배열)
  votedKeywords   # [] (동)
}
total, score (null), starDistribution (null)
```

```
visitorReviewStats {
  review { avgRating totalCount authorCount imageReviewCount }
  analysis {
    themes: []                # 빈 배열
    menus: []                 # 빈 배열
    votedKeyword.totalCount: null   # 병원 카테고리는 통계 미제공
    votedKeyword.details: []
  }
  visitorReviewsTotal ratingReviewsTotal
}
```

**결론**: 본문 raw·rating(null)·visitedDate·author 익명·avgRating·imageReviewCount 는 안정 수집.
**키워드 빈도/테마 집계는 네이버가 병원 카테고리에 미제공** → 우리 측에서 후기 본문 raw 로 LLM·임베딩 자체 추출.

## photoViewer 응답 핵심 필드

```
photos[] {
  originalUrl     # 사진 URL
  photoType       # "ibu" (병원 공식) | "visitor" (방문자) | "ugc" (외부 블로그)
  mediaType       # null | "video"
  title           # 사진 캡션
  text            # 후기 본문 일부 (visitor) | 블로그 제목 (ugc)
  desc            # 추가 설명
  author.nickname # 작성자
  author.from     # "NAVER" (visitor) | null
  businessName    # "자생한방병원" (ibu 만)
  externalLink {  # ugc(블로그) 일 때
    title: "블로그"
    url: "https://blog.naver.com/..."  # ★ 블로그 시그널 시드 URL
  }
  sourceTitle     # "블로그" 등
}
```

```
photoTabFilters.tabFilters[] {
  item            # "업체" | "AI View" | "리뷰"
  subTabFilters[] {
    item: "내부" code: "INTERIOR"
    item: "외부" code: "EXTERIOR"
    # 카테고리 따라 더 세분화 가능
  }
}
```

**ugc 채널 = 블로그 시그널 시드 URL 자동 큐레이션** (`v1/search/blog` 보다 정확한 매칭).
**AI View = 네이버가 사진 자동 분류** (내부·외부 등). 박스 2 Vision 입력에 직접 시그널.

## ncpt 토큰 발급 흐름 (Playwright 가 자동)

1. 검색 페이지(`map.naver.com/p/search/{query}`) 진입
2. SDK 가 `GET ncpt.naver.com/static/ncaptcha-api.js?ncaptcha-sitekey={140자}` 로딩
3. `POST ncpt.naver.com/v2/tokens?q={ts}&tid={11자}`, body `{"cipherText":"<클라이언트 환경 시그너처 600+자>"}`
4. 응답 `{"tokenId":"<base64 76자>"}`
5. SDK 가 추가 가공해 검색 URL 의 `token={44자 base64+=}` 박음
6. `GET map.naver.com/p/api/search/allSearch?...&token={44자}&sscode=svc.mapv5.search` HTTP 200

**httpx 단독 호출 = 불가능** (cipherText 생성 못함, `CE_BAD_REQUEST` 차단).
**Playwright = 자동 동작**.

## GraphQL 호출 후속

place_id 받은 후 `pcmap.place.naver.com/hospital/{id}/review/visitor` 또는 `/photo` 페이지 진입 → 쿠키·세션 굳히기 → `page.evaluate fetch('https://pcmap-api.place.naver.com/graphql', { credentials: 'include' })` 로 직접 POST.

## EC2 시스템 의존성 (Playwright Chromium)

```bash
sudo dnf install -y atk at-spi2-atk nss cups-libs libdrm libXcomposite \
    libXdamage libXrandr libXfixes libXScrnSaver libxkbcommon mesa-libgbm \
    pango cairo alsa-lib
```

(2026-05-28 EC2 에 설치 완료)

## 미해명 항목 (다음 세션)

- 정보 탭 (`진료영역` · `대표 키워드` · `원장 이력` · `편의시설`) query 명 — `/home` · `/information` 탭 진입 시 호출되는 GraphQL 캡처
- 카카오 비공식 엔드포인트 (`place.map.kakao.com/main/v/{id}`) 의 실제 place_id 형식·ncpt-style 차단 여부
- 1만 풀커버 시 EC2 IP rate-limit 임계
- `visitorReviews` query 에 `cidList` 박아도 themes/votedKeyword 가 빈 배열인 이유 → "네이버가 병원 카테고리에 통계 미제공" 으로 확정. **uncommon 카테고리(미용·치과 등)에서는 채워질 가능성** 다음 세션 표본 확장 시 검증
