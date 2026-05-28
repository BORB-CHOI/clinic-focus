# Design Document

> ⚠️ **부분 변경 (2026-05-28)**: 아래 ②의 **카카오 홈페이지 추출은 Playwright `KakaoPlaceRenderer` → httpx `panel3` 로 대체**됨.
> 카카오 비공식 `place-api.map.kakao.com/places/panel3/{id}` 가 `summary.homepages` 를 단발 httpx 로 직접 주므로 브라우저 렌더링 불필요.
> `enrich_urls.py` 2단계는 이제 `KakaoPlaceAdapter.fetch_panel3` + `extract_homepage`(`be/adapters/kakao_place_adapter.py`)를 쓴다.
> `kakao_place_renderer.py` 는 호출부 0(고아) — 폐기 후보. **단 BrowserManager·JSRenderer(자체 사이트 SPA 렌더링)는 그대로 유효**.
> 자세한 건 `docs/plans/task-queue.md` Phase B 카카오 raw 노트(사실 14·17·24) 참조.

## Overview

Playwright 기반 브라우저 렌더링을 기존 URL 보강 및 크롤링 파이프라인에 통합하여:
1. ~~카카오 장소 페이지에서 홈페이지 URL 추출 (Playwright)~~ → **httpx panel3 로 대체 (위 노트)**
2. SPA 병원 홈페이지 크롤링 성공률 향상 (~50% → 90%+) — **유효 (BrowserManager + JSRenderer)**
3. 네이버 쿼리 다변화로 히트율 개선 (1.3% → 예상 3~5%) — 유효

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Enrichment Pipeline                            │
│  (be/scripts/enrich_urls.py)                                     │
│                                                                   │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Naver Search │    │ Kakao Search     │    │ URL Validator │  │
│  │ (multi-query)│───▶│ + Place Renderer │───▶│ (HEAD check)  │  │
│  └──────────────┘    └──────────────────┘    └───────────────┘  │
│         │                     │                       │          │
│         ▼                     ▼                       ▼          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    DynamoDB                               │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Crawl Pipeline                                 │
│  (be/scripts/crawl_all.py)                                       │
│                                                                   │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │ Static Crawler   │    │ JS Renderer      │                   │
│  │ (httpx + BS4)    │───▶│ (Playwright)     │                   │
│  │                  │    │ fallback         │                   │
│  └──────────────────┘    └──────────────────┘                   │
│         │                         │                              │
│         ▼                         ▼                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              S3 (crawl data JSON)                         │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 Playwright Browser Manager                        │
│  (be/core/browser_manager.py)                                    │
│                                                                   │
│  - Singleton browser instance per pipeline run                   │
│  - Headless Chromium                                             │
│  - Auto-restart every 200 pages                                  │
│  - 30s per-page timeout                                          │
│  - Max 3 concurrent tabs                                         │
│  - Crash recovery                                                │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **URL Enrichment Flow:**
   - DynamoDB scan → hospitals without URL
   - Naver multi-query search (name+구 → name only → name+동)
   - URL validation (HEAD request)
   - If Naver fails → Kakao search → place_url → Playwright render → extract homepage
   - URL validation (HEAD request)
   - Save to DynamoDB

2. **Crawl Flow:**
   - DynamoDB scan → hospitals with URL
   - Static fetch (httpx)
   - If text < 100 chars → Playwright render
   - Store CrawlData to S3 with render_method metadata

## Components and Interfaces

### 1. BrowserManager (`be/core/browser_manager.py`)

새로운 모듈. Playwright 브라우저 인스턴스의 생명주기를 관리하는 async context manager.

```python
class BrowserManager:
    """Playwright 브라우저 인스턴스 관리."""
    
    MAX_PAGES_BEFORE_RESTART: int = 200
    PAGE_TIMEOUT_MS: int = 30_000
    MAX_CONCURRENT_TABS: int = 3
    
    async def __aenter__(self) -> "BrowserManager"
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
    async def render_page(self, url: str, wait_until: str = "networkidle") -> str | None
    async def extract_element_attr(self, url: str, selector: str, attr: str) -> str | None
    async def _ensure_browser(self) -> None
    async def _restart_browser(self) -> None
```

### 2. KakaoPlaceRenderer (`be/adapters/kakao_place_renderer.py`)

새로운 모듈. 카카오 장소 페이지에서 홈페이지 URL을 추출.

```python
class KakaoPlaceRenderer:
    """카카오 장소 페이지 Playwright 렌더링 → 홈페이지 URL 추출."""
    
    HOMEPAGE_SELECTORS: list[str]  # 여러 후보 CSS 셀렉터
    TIMEOUT_MS: int = 15_000
    
    def __init__(self, browser_manager: BrowserManager)
    async def extract_homepage_url(self, place_url: str) -> str | None
```

### 3. NaverMapAdapter 확장 (`be/adapters/naver_map_adapter.py`)

기존 모듈 수정. 쿼리 다변화 로직 추가.

```python
class NaverMapAdapter:
    # 기존 메서드 유지
    def search_hospital(self, name: str, address: str = "") -> dict | None
    
    # 새 메서드
    def search_hospital_multi_query(self, name: str, address: str = "") -> dict | None
    
    @staticmethod
    def _extract_dong(address: str) -> str
    
    @staticmethod
    def _sanitize_name(name: str) -> str
```

### 4. JSRenderer (`be/core/js_renderer.py`)

새로운 모듈. 병원 홈페이지 JS 렌더링 전용.

```python
class JSRenderer:
    """SPA 병원 홈페이지 Playwright 렌더링."""
    
    def __init__(self, browser_manager: BrowserManager)
    async def render_and_extract(self, url: str) -> tuple[str, BeautifulSoup] | None
```

### 5. URLValidator (`be/core/url_validator.py`)

새로운 모듈. URL 유효성 검증.

```python
class URLValidator:
    """URL 접근 가능성 및 유효성 검증."""
    
    BLOCKED_DOMAINS: list[str]
    TIMEOUT_SECONDS: float = 10.0
    
    async def validate(self, url: str) -> str | None
    def _is_blocked_domain(self, url: str) -> bool
```

### 6. Crawler 확장 (`be/core/crawler.py`)

기존 모듈 수정.

```python
async def crawl_one_hospital(
    hospital_id: str,
    website_url: str,
    http_client: httpx.AsyncClient,
    browser_manager: BrowserManager | None = None,  # 새 파라미터
) -> CrawlData
```

## Data Models

### CrawledPage (수정)

```python
class CrawledPage(BaseModel):
    url: str
    page_type: Literal["main", "about", "service", "doctors", "blog", "other"]
    html_text: str
    fetched_at: datetime
    render_method: Literal["static", "playwright"] = "static"  # 새 필드
```

### EnrichmentResult (새 모델, 리포트용)

```python
class EnrichmentResult(BaseModel):
    total_processed: int
    naver_found: int
    kakao_found: int
    validation_rejected: int
    remaining_no_url: int
    hit_rate: float
```

### CrawlSummary (새 모델, 리포트용)

```python
class CrawlSummary(BaseModel):
    total_hospitals: int
    static_success: int
    js_render_success: int
    failed: int
    crawl_success_rate: float
```

## Error Handling

| Error Scenario | Component | Handling Strategy |
|---|---|---|
| Playwright browser crash | BrowserManager | 새 인스턴스 생성 후 현재 병원부터 재시도 |
| 페이지 렌더링 30초 초과 | BrowserManager | 해당 page context 종료, None 반환, 다음 페이지 진행 |
| 카카오 장소 페이지 15초 초과 | KakaoPlaceRenderer | None 반환, 다음 병원 진행 |
| 네이버 API 호출 실패 | NaverMapAdapter | None 반환, 다음 병원 진행 (기존 동작 유지) |
| URL HEAD 요청 타임아웃 | URLValidator | URL 폐기, None 반환 |
| URL HEAD 요청 4xx/5xx | URLValidator | URL 폐기, None 반환 |
| DynamoDB 쓰기 실패 | Enrichment_Pipeline | 에러 로그 후 다음 병원 진행 |
| 메모리 부족 (Chromium) | BrowserManager | 200페이지 재시작으로 예방, 크래시 시 복구 |

## Correctness Properties

### Property 1: URL Protocol Validation
**Validates: Requirements 1.5**
For all URLs extracted by Kakao_Place_Renderer, the URL starts with "http://" or "https://". Any URL not matching this pattern is discarded (returns None).

### Property 2: Query Variant Short-Circuit
**Validates: Requirements 2.3**
For all hospitals where query variant N produces a valid result, query variants N+1 through K are never executed. The adapter stops at the first successful match.

### Property 3: Special Character Sanitization
**Validates: Requirements 2.5**
For all hospital names processed by the multi-query search, the constructed query string contains no parentheses, brackets, or special characters that could interfere with search API matching.

### Property 4: Static-First Guarantee
**Validates: Requirements 3.6**
For all pages processed by the Crawler, static fetching (httpx) is always attempted before JS rendering (Playwright). Playwright is only invoked when static text length is below 100 characters.

### Property 5: Pipeline Deduplication
**Validates: Requirements 4.2**
For all hospitals processed by the Enrichment_Pipeline, if Naver search finds a valid URL, that hospital is not processed by the Kakao step. No hospital appears in both the Naver-found set and the Kakao-processed set.

### Property 6: Pipeline Idempotence
**Validates: Requirements 4.5**
Running the Enrichment_Pipeline twice on the same dataset produces the same final state in DynamoDB. Hospitals that already have URLs are skipped on subsequent runs.

### Property 7: Render Method Traceability
**Validates: Requirements 5.5**
For all CrawledPage records produced by the Crawler, the render_method field is either "static" or "playwright", and it accurately reflects which method was used to obtain the content.

### Property 8: Browser Restart Cadence
**Validates: Requirements 6.5**
The BrowserManager restarts the browser instance after every 200 pages processed. The page counter resets to 0 after each restart.

### Property 9: URL Validation Completeness
**Validates: Requirements 7.1, 7.2**
For all URLs saved to DynamoDB by the Enrichment_Pipeline, the URL has been verified to return a 2xx or 3xx HTTP status code, and its final domain is not in the blocked domains list.

### Property 10: Redirect Resolution
**Validates: Requirements 7.4**
For all URLs that redirect, the Enrichment_Pipeline stores the final redirected URL (not the original), ensuring the stored URL directly reaches the hospital's content.

## Testing Strategy

- **Unit tests**: URLValidator, 쿼리 변형 로직, 특수문자 제거 — mock HTTP 응답 사용
- **Integration tests**: BrowserManager 생명주기, KakaoPlaceRenderer (실제 Playwright 사용, 로컬 HTML fixture)
- **Property tests**: URL 프로토콜 검증, 쿼리 단축 회로, 파이프라인 멱등성
- **E2E smoke test**: 소수 병원(5개)으로 전체 파이프라인 실행 확인

## Dependencies

### New Dependencies
- `playwright` — 브라우저 자동화 (Chromium headless)
- `playwright install chromium` 실행 필요 (post-install step)

### Existing Dependencies (변경 없음)
- `httpx` — HTTP 클라이언트
- `beautifulsoup4` — HTML 파싱
- `boto3` — AWS DynamoDB/S3
- `pydantic` — 데이터 모델

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `be/core/browser_manager.py` | Create | Playwright 브라우저 인스턴스 관리 |
| `be/core/js_renderer.py` | Create | SPA 페이지 JS 렌더링 |
| `be/core/url_validator.py` | Create | URL 유효성 검증 |
| `be/adapters/kakao_place_renderer.py` | Create | 카카오 장소 페이지 홈페이지 추출 |
| `be/adapters/naver_map_adapter.py` | Modify | 쿼리 다변화 메서드 추가 |
| `be/core/crawler.py` | Modify | JS 렌더링 폴백 통합 |
| `be/scripts/enrich_urls.py` | Modify | Playwright 기반 카카오 단계 + URL 검증 통합 |
| `be/scripts/crawl_all.py` | Modify | JS 렌더링 폴백 통합 + 리포트 개선 |
| `shared/models.py` | Modify | CrawledPage에 render_method 필드 추가 |
| `requirements.txt` | Modify | playwright 추가 |
