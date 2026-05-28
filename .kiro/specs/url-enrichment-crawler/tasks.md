# Implementation Plan: URL Enrichment Crawler

## Overview

Playwright 기반 브라우저 렌더링을 도입하여 병원 홈페이지 URL 보강 히트율과 크롤링 성공률을 개선한다. 7개 태스크로 구성되며, 기반 인프라(Task 1) → 개별 컴포넌트(Task 2~4) → 통합(Task 5~7) 순서로 진행한다.

## Tasks

- [x] 1. Playwright 설치 및 BrowserManager 구현
  - [x] 1.1 requirements.txt에 playwright 추가
  - [x] 1.2 BrowserManager 모듈 생성 (`be/core/browser_manager.py`) — async context manager, Chromium headless, 200페이지 재시작, 30초 타임아웃, Semaphore(3) 동시 탭 제한, 크래시 복구
  - [x] 1.3 CrawledPage 모델에 render_method 필드 추가 (`shared/models.py`) — Literal["static", "playwright"] = "static"
  - [x] 1.4 BrowserManager 단위 테스트 작성 — 생명주기(enter/exit), 200페이지 재시작 카운터, 타임아웃 처리
- [x] 2. 네이버 검색 쿼리 다변화
  - [x] 2.1 NaverMapAdapter에 search_hospital_multi_query 메서드 추가 — 쿼리 순서: name+구 → name만 → name+동
  - [x] 2.2 주소에서 동명 추출 로직 구현 — "(대치동)" 또는 주소 파싱으로 동 추출
  - [x] 2.3 병원명 특수문자 제거 로직 추가 — 괄호, 특수기호 제거
  - [x] 2.4 쿼리 다변화 단위 테스트 — 각 변형 순서 확인, 첫 매칭 시 중단 확인, 특수문자 제거 확인
- [x] 3. 카카오 장소 페이지 홈페이지 URL 추출
  - [x] 3.1 KakaoPlaceRenderer 모듈 생성 (`be/adapters/kakao_place_renderer.py`) — BrowserManager 주입, 셀렉터 기반 홈페이지 링크 추출
  - [x] 3.2 카카오 장소 페이지 셀렉터 조사 및 구현 — 여러 후보 셀렉터 순차 시도
  - [x] 3.3 URL 프로토콜 검증 로직 — http/https 아닌 URL 필터링
  - [x] 3.4 KakaoPlaceRenderer 테스트 — 로컬 HTML fixture로 추출 로직 검증
- [x] 4. URL 유효성 검증
  - [x] 4.1 URLValidator 모듈 생성 (`be/core/url_validator.py`) — HEAD 요청, 리다이렉트 추적, 10초 타임아웃
  - [x] 4.2 차단 도메인 목록 구현 — map.naver.com, map.daum.net, google.com 등
  - [x] 4.3 HEAD 실패 시 GET 폴백 구현
  - [x] 4.4 URLValidator 단위 테스트 — 2xx 통과, 4xx/5xx 거부, 타임아웃 거부, 리다이렉트 추적, 차단 도메인 거부
- [x] 5. JS 렌더링 크롤러 통합
  - [x] 5.1 JSRenderer 모듈 생성 (`be/core/js_renderer.py`) — BrowserManager 주입, networkidle 대기, text+soup 반환
  - [x] 5.2 crawler.py 수정 — crawl_one_hospital에 browser_manager 파라미터 추가, 정적 < 100자 시 JS 폴백
  - [x] 5.3 메인 페이지 JS 필요 시 서브페이지도 Playwright 사용하도록 로직 추가
  - [x] 5.4 render_method 필드 기록 로직 추가
  - [x] 5.5 JS 렌더링 크롤러 통합 테스트 — 정적 성공 케이스, JS 폴백 케이스, 렌더 실패 케이스
- [x] 6. 보강 파이프라인 통합 (enrich_urls.py)
  - [x] 6.1 enrich_urls.py를 async로 전환 — asyncio.run(main()) 패턴
  - [x] 6.2 네이버 단계에서 search_hospital_multi_query 사용하도록 변경
  - [x] 6.3 카카오 단계에 KakaoPlaceRenderer + Playwright 통합 — ⚠️ **2026-05-28 대체**: httpx `panel3` (`KakaoPlaceAdapter.fetch_panel3` + `extract_homepage`)로 전환, Playwright 렌더링 제거 (design.md 상단 노트)
  - [x] 6.4 URL 발견 후 URLValidator로 검증 단계 추가
  - [x] 6.5 중단 재개 로직 — DynamoDB에서 이미 URL 있는 병원 스킵
  - [x] 6.6 최종 리포트 출력 개선 — 소스별 발견 수, 히트율, 잔여 병원 수
- [x] 7. 크롤링 파이프라인 통합 (crawl_all.py)
  - [x] 7.1 crawl_all.py에 BrowserManager 통합 — async with 패턴
  - [x] 7.2 JS 렌더링 필요 병원 자동 Playwright 폴백 적용
  - [x] 7.3 크롤링 리포트 개선 — 정적 성공, JS 성공, 실패 각각 카운트 및 성공률 출력
  - [x] 7.4 전체 파이프라인 E2E 스모크 테스트 — 5개 병원으로 enrich → crawl 전체 흐름 확인

## Task Dependencies

```yaml
2. 네이버 검색 쿼리 다변화:
  - 1. Playwright 설치 및 BrowserManager 구현
3. 카카오 장소 페이지 홈페이지 URL 추출:
  - 1. Playwright 설치 및 BrowserManager 구현
4. URL 유효성 검증:
  - 1. Playwright 설치 및 BrowserManager 구현
5. JS 렌더링 크롤러 통합:
  - 1. Playwright 설치 및 BrowserManager 구현
6. 보강 파이프라인 통합 (enrich_urls.py):
  - 2. 네이버 검색 쿼리 다변화
  - 3. 카카오 장소 페이지 홈페이지 URL 추출
  - 4. URL 유효성 검증
7. 크롤링 파이프라인 통합 (crawl_all.py):
  - 5. JS 렌더링 크롤러 통합
```

## Notes

- Playwright 설치 시 `playwright install chromium` 명령이 필요하며, CI/CD 환경에서는 시스템 의존성(libnss3 등)도 설치해야 함
- 카카오 장소 페이지의 DOM 구조는 변경될 수 있으므로, 셀렉터를 설정 파일로 분리하는 것을 권장
- 네이버 API 초당 10회 제한은 쿼리 변형 시에도 동일하게 적용되므로, 3개 변형 시도 시 병원당 최대 0.36초 소요
- 대량 처리(1,700+ 병원) 시 카카오 Playwright 단계는 약 7~8시간 소요 예상 (병원당 ~15초)
