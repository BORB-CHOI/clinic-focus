# Requirements Document

## Introduction

병원 홈페이지 URL 보강 및 크롤링 성공률 개선 시스템. 현재 강남구 2,442개 병원 중 URL 보유율 29.4%(718개)이며, URL이 있는 병원도 ~50%가 JS 렌더링 문제로 크롤링에 실패한다. 본 기능은 Playwright 기반 브라우저 렌더링을 도입하여 (1) 카카오 장소 페이지에서 홈페이지 URL을 추출하고, (2) SPA 기반 병원 홈페이지의 크롤링 성공률을 90% 이상으로 끌어올리며, (3) 네이버 검색 쿼리 전략을 다변화하여 히트율을 개선한다.

## Glossary

- **Enrichment_Pipeline**: 병원 홈페이지 URL이 없는 레코드에 대해 외부 검색 API와 브라우저 렌더링을 활용하여 URL을 찾아 DynamoDB에 저장하는 파이프라인
- **Naver_Search_Adapter**: 네이버 지역 검색 API(openapi.naver.com/v1/search/local.json)를 호출하여 병원 정보를 조회하는 어댑터
- **Kakao_Search_Adapter**: 카카오 로컬 검색 API(dapi.kakao.com/v2/local/search/keyword.json)를 호출하여 병원 장소 정보를 조회하는 어댑터
- **Kakao_Place_Renderer**: Playwright를 사용하여 카카오 장소 페이지(place.map.kakao.com/{id})를 렌더링하고 홈페이지 URL을 추출하는 컴포넌트
- **JS_Renderer**: Playwright를 사용하여 SPA 기반 병원 홈페이지를 렌더링하고 텍스트 콘텐츠를 추출하는 컴포넌트
- **Crawler**: 병원 홈페이지에서 텍스트, 이미지, 서브페이지를 수집하는 크롤링 엔진
- **Hospital_Record**: DynamoDB Hospitals 테이블의 단일 병원 레코드 (HospitalMeta 모델)
- **CrawlData**: 크롤링 결과를 담는 Pydantic 모델 (pages, images, public_data 포함)
- **Hit_Rate**: URL 보강 시도 대비 실제 URL을 발견한 비율
- **Crawl_Success_Rate**: 크롤링 시도 대비 유효한 텍스트(100자 이상)를 추출한 비율
- **Query_Variant**: 동일 병원에 대해 검색 정확도를 높이기 위해 생성하는 다양한 검색 쿼리 형태 (이름만, 이름+구, 이름+동 등)

## Requirements

### Requirement 1: Playwright 기반 카카오 장소 페이지 홈페이지 URL 추출

**User Story:** As a 데이터 엔지니어, I want 카카오 장소 페이지에서 홈페이지 URL을 자동 추출하고 싶다, so that 카카오에만 등록된 병원의 홈페이지도 보강할 수 있다.

#### Acceptance Criteria

1. WHEN the Kakao_Search_Adapter returns a place_url for a hospital, THE Kakao_Place_Renderer SHALL render the page using Playwright and extract the homepage URL from the rendered DOM
2. WHEN the rendered Kakao place page contains a homepage link element, THE Kakao_Place_Renderer SHALL return the extracted URL as a string
3. WHEN the rendered Kakao place page does not contain a homepage link element, THE Kakao_Place_Renderer SHALL return None within 15 seconds
4. IF Playwright fails to load the Kakao place page within 15 seconds, THEN THE Kakao_Place_Renderer SHALL log the timeout error and return None
5. IF the extracted URL does not start with "http://" or "https://", THEN THE Kakao_Place_Renderer SHALL discard the URL and return None
6. THE Kakao_Place_Renderer SHALL reuse a single browser instance across multiple place page extractions within one pipeline run to minimize resource usage

### Requirement 2: 네이버 검색 쿼리 다변화

**User Story:** As a 데이터 엔지니어, I want 네이버 검색 쿼리를 여러 변형으로 시도하고 싶다, so that 단일 쿼리로 찾지 못하는 병원도 발견할 수 있다.

#### Acceptance Criteria

1. WHEN the primary query "병원명 + 구" returns no matching result, THE Naver_Search_Adapter SHALL retry with Query_Variant "병원명만" (이름 단독)
2. WHEN both "병원명 + 구" and "병원명만" queries return no matching result, THE Naver_Search_Adapter SHALL retry with Query_Variant "병원명 + 동명" (주소에서 동 추출)
3. THE Naver_Search_Adapter SHALL stop retrying as soon as a matching result with a valid homepage link is found
4. THE Naver_Search_Adapter SHALL maintain the existing rate limit of 0.12 seconds between API calls regardless of query variant count
5. WHEN a hospital name contains parentheses or special characters, THE Naver_Search_Adapter SHALL remove them before constructing the query

### Requirement 3: Playwright 기반 JS 렌더링 크롤링

**User Story:** As a 데이터 엔지니어, I want SPA 기반 병원 홈페이지도 정상적으로 크롤링하고 싶다, so that 크롤링 성공률을 90% 이상으로 올릴 수 있다.

#### Acceptance Criteria

1. WHEN the static crawler (httpx + BeautifulSoup) extracts less than 100 characters of text from a page, THE JS_Renderer SHALL render the page using Playwright and re-extract the text content
2. WHEN the JS_Renderer renders a page, THE JS_Renderer SHALL wait for the DOM content to stabilize (no new network requests for 2 seconds or maximum 15 seconds total)
3. WHEN the JS_Renderer successfully extracts 100 characters or more of text, THE Crawler SHALL use the Playwright-rendered content as the page result
4. IF the JS_Renderer fails to extract 100 characters or more after rendering, THEN THE Crawler SHALL mark the page as "render_failed" and skip the page
5. THE JS_Renderer SHALL reuse a single browser instance across multiple page renderings within one crawl session
6. THE Crawler SHALL attempt static fetching first for every page before falling back to JS rendering to minimize resource usage
7. WHILE the JS_Renderer is processing pages, THE JS_Renderer SHALL limit concurrent browser tabs to 3 to prevent memory exhaustion

### Requirement 4: 보강 파이프라인 실행 순서 및 통합

**User Story:** As a 데이터 엔지니어, I want URL 보강 파이프라인이 네이버 → 카카오(Playwright) 순서로 자동 실행되고 결과를 리포트하길 원한다, so that 한 번의 실행으로 전체 보강 작업을 완료할 수 있다.

#### Acceptance Criteria

1. THE Enrichment_Pipeline SHALL execute in the order: (1) Naver search with query variants, (2) Kakao search with Playwright rendering
2. WHEN step 1 (Naver) finds a URL for a hospital, THE Enrichment_Pipeline SHALL skip that hospital in step 2 (Kakao)
3. WHEN the Enrichment_Pipeline completes, THE Enrichment_Pipeline SHALL print a summary report containing: total hospitals processed, URLs found per source (Naver, Kakao), final hit rate, and remaining hospitals without URLs
4. THE Enrichment_Pipeline SHALL save each discovered URL to DynamoDB immediately after validation, not in batch at the end
5. IF the Enrichment_Pipeline is interrupted, THEN THE Enrichment_Pipeline SHALL resume from the last unprocessed hospital on the next run by checking existing URLs in DynamoDB

### Requirement 5: 크롤링 파이프라인 JS 렌더링 통합

**User Story:** As a 데이터 엔지니어, I want 크롤링 파이프라인이 JS 렌더링 실패 사이트를 자동으로 Playwright로 재시도하길 원한다, so that 수동 개입 없이 높은 성공률을 달성할 수 있다.

#### Acceptance Criteria

1. THE Crawler SHALL first attempt static fetching (httpx + BeautifulSoup) for the main page of each hospital
2. WHEN static fetching yields less than 100 characters of text, THE Crawler SHALL automatically invoke the JS_Renderer for that page
3. WHEN the JS_Renderer succeeds for the main page, THE Crawler SHALL use Playwright for all subsequent subpages of that hospital
4. WHEN the crawl session completes, THE Crawler SHALL print a summary containing: total hospitals, static success count, JS render success count, total failure count, and overall Crawl_Success_Rate
5. THE Crawler SHALL store a "render_method" field ("static" or "playwright") in each CrawledPage record for traceability

### Requirement 6: Playwright 리소스 관리 및 안정성

**User Story:** As a 데이터 엔지니어, I want Playwright 브라우저 리소스가 안정적으로 관리되길 원한다, so that 대량 처리 시 메모리 누수나 좀비 프로세스 없이 파이프라인이 완료된다.

#### Acceptance Criteria

1. THE JS_Renderer SHALL launch Playwright in headless mode with Chromium browser
2. WHEN the pipeline run starts, THE JS_Renderer SHALL create one browser instance and reuse it for all pages in that run
3. WHEN the pipeline run completes (success or failure), THE JS_Renderer SHALL close the browser instance and release all resources
4. IF a single page rendering exceeds 30 seconds, THEN THE JS_Renderer SHALL terminate that page context and proceed to the next page
5. WHEN the browser instance has processed 200 pages, THE JS_Renderer SHALL restart the browser instance to prevent memory accumulation
6. IF the browser instance crashes unexpectedly, THEN THE JS_Renderer SHALL create a new browser instance and continue processing from the current hospital

### Requirement 7: URL 유효성 검증

**User Story:** As a 데이터 엔지니어, I want 발견된 URL이 실제로 접근 가능한 병원 홈페이지인지 검증하고 싶다, so that 잘못된 URL이 DynamoDB에 저장되지 않는다.

#### Acceptance Criteria

1. WHEN the Enrichment_Pipeline discovers a new URL, THE Enrichment_Pipeline SHALL send an HTTP HEAD request to verify the URL returns a 2xx or 3xx status code
2. IF the URL returns a 4xx or 5xx status code, THEN THE Enrichment_Pipeline SHALL discard the URL and not save it to DynamoDB
3. IF the URL does not respond within 10 seconds, THEN THE Enrichment_Pipeline SHALL discard the URL
4. WHEN the URL redirects to a different domain, THE Enrichment_Pipeline SHALL use the final redirected URL for storage
5. IF the final URL domain matches a known non-hospital domain (naver.com map subdomain, daum.net, google.com), THEN THE Enrichment_Pipeline SHALL discard the URL
