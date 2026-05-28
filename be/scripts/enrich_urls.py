"""강남구 병원 홈페이지 URL 보강 — 네이버 + 카카오 2단계 (async).

실행 순서:
  1단계: 네이버 지역 검색 API → search_hospital_multi_query (쿼리 다변화)
  2단계: 카카오 로컬 검색 API → place_id → panel3 상세 API → summary.homepages 추출
         (Playwright 제거 — panel3 httpx 단발이 homepages 를 직접 줌)

URL 발견 후 URLValidator로 검증 → 유효한 경우만 DynamoDB 저장.

실행 전 .env 확인:
  NAVER_MAP_CLIENT_ID, NAVER_MAP_CLIENT_SECRET  (1단계 필수)
  KAKAO_REST_API_KEY                            (2단계 필수)
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

# 터미널에 즉시 출력 (버퍼링 끄기)
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.kakao_adapter import KakaoAdapter
from be.adapters.kakao_place_adapter import KakaoPlaceAdapter, extract_homepage
from be.adapters.naver_map_adapter import NaverMapAdapter
from be.core.url_validator import URLValidator


NAVER_KEY = os.environ.get("NAVER_MAP_CLIENT_ID", "")
KAKAO_KEY = os.environ.get("KAKAO_REST_API_KEY", "")

# 네이버 link 필드에서 실제 홈페이지로 인정하지 않을 도메인들
# 네이버 블로그는 병원의 공식 온라인 채널로 인정 — 자칭 컨셉 추출 소스로 유효
NAVER_SKIP_DOMAINS = ("map.naver.com", "search.naver.com", "news.naver.com")


def _is_real_website(url: str) -> bool:
    """실제 병원 홈페이지 URL인지 판단.
    blog.naver.com은 허용 — 홈페이지 없는 병원의 공식 채널로 인정.
    """
    if not url or not url.startswith("http"):
        return False
    return not any(d in url for d in NAVER_SKIP_DOMAINS)


async def run_step1_naver(
    db: DynamoAdapter,
    no_url: list,
    validator: URLValidator,
    *,
    dry_run: bool = False,
) -> tuple[int, int, list]:
    """1단계: 네이버 지역 검색 (쿼리 다변화) → 홈페이지 URL 보강.

    Returns:
        (naver_found, validation_rejected, still_missing)
    """
    if not NAVER_KEY:
        print("  ⚠️  NAVER_MAP_CLIENT_ID 미설정 — 1단계 건너뜀")
        return 0, 0, no_url

    naver = NaverMapAdapter()
    found = 0
    rejected = 0
    still_missing = []
    total = len(no_url)
    start_time = time.time()

    for i, hospital in enumerate(no_url, 1):
        result = naver.search_hospital_multi_query(hospital.name, hospital.location.address)
        link = (result or {}).get("link", "")

        if _is_real_website(link):
            # URL 유효성 검증
            validated_url = await validator.validate(link)
            if validated_url:
                if not dry_run:
                    db.update_website_url(hospital.hospital_id, validated_url)
                found += 1
                print(f"  [{i}/{total}] ✅ {hospital.name} → {validated_url}")
            else:
                rejected += 1
                still_missing.append(hospital)
        else:
            still_missing.append(hospital)

        # 50개마다 진행률 + ETA 출력
        if i % 50 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            remaining_count = total - i
            eta_seconds = remaining_count / rate if rate > 0 else 0
            eta_min = int(eta_seconds // 60)
            eta_sec = int(eta_seconds % 60)
            pct = i / total * 100
            print(
                f"  📊 [{i}/{total}] {pct:.0f}% | "
                f"발견: {found} | 검증실패: {rejected} | "
                f"속도: {rate:.1f}건/초 | ETA: {eta_min}분 {eta_sec}초"
            )

    return found, rejected, still_missing


async def run_step2_kakao(
    db: DynamoAdapter,
    no_url: list,
    validator: URLValidator,
    *,
    dry_run: bool = False,
) -> tuple[int, int]:
    """2단계: 카카오 로컬 검색 → place_id → panel3 상세 → summary.homepages 보강.

    panel3 의 `summary.homepages` 가 홈페이지·SNS·블로그·카페 URL 을 직접 주므로
    `extract_homepage` 로 자체 도메인 1개를 골라 검증·저장한다 (Playwright 불필요).

    Returns:
        (kakao_found, validation_rejected)
    """
    if not KAKAO_KEY:
        print("  ⚠️  KAKAO_REST_API_KEY 미설정 — 2단계 건너뜀")
        return 0, 0

    kakao = KakaoAdapter()
    place_adapter = KakaoPlaceAdapter()
    found = 0
    rejected = 0
    total = len(no_url)
    start_time = time.time()

    try:
        for i, hospital in enumerate(no_url, 1):
            kakao_info = kakao.search_hospital(hospital.name, hospital.location.address)
            place_id = str((kakao_info or {}).get("id", ""))

            if not place_id:
                await asyncio.sleep(0.15)
            else:
                # panel3 상세 API → summary.homepages 에서 자체 홈페이지 추출
                panel3 = place_adapter.fetch_panel3(place_id)
                homepage = extract_homepage(panel3) if panel3 else None

                if homepage:
                    validated_url = await validator.validate(homepage)
                    if validated_url:
                        if not dry_run:
                            db.update_website_url(hospital.hospital_id, validated_url)
                        found += 1
                        print(f"  [{i}/{total}] ✅ {hospital.name} → {validated_url}")
                    else:
                        rejected += 1

                # 회색지대 API — 요청 간격 유지 (rate-limit 미실측)
                await asyncio.sleep(0.3)

            # 20개마다 진행률 + ETA 출력
            if i % 20 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining_count = total - i
                eta_seconds = remaining_count / rate if rate > 0 else 0
                eta_min = int(eta_seconds // 60)
                eta_sec = int(eta_seconds % 60)
                pct = i / total * 100
                print(
                    f"  📊 [{i}/{total}] {pct:.0f}% | "
                    f"발견: {found} | 검증실패: {rejected} | "
                    f"속도: {rate:.1f}건/초 | ETA: {eta_min}분 {eta_sec}초"
                )
    finally:
        place_adapter.close()

    return found, rejected


async def main() -> None:
    db = DynamoAdapter()
    validator = URLValidator()

    print("=" * 60)
    print("홈페이지 URL 보강 — 강남구")
    print("=" * 60)

    # 1. 강남구 전체 META 조회 (sigungu-index GSI)
    print("\nDynamoDB에서 강남구 병원 조회 중...")
    hospitals = db.list_hospitals_by_sigungu("강남구")

    with_url = [h for h in hospitals if h.contact.website_url]
    no_url   = [h for h in hospitals if not h.contact.website_url]

    print(f"  전체: {len(hospitals)}개")
    print(f"  기존 URL 있음: {len(with_url)}개 (스킵)")
    print(f"  URL 없음 → 보강 대상: {len(no_url)}개")

    # ── 1단계: 네이버 (쿼리 다변화) ──────────────────────────────
    print(f"\n[ 1단계 ] 네이버 지역 검색 — 쿼리 다변화 ({len(no_url)}개 대상)")
    print("-" * 60)
    naver_found, naver_rejected, still_missing = await run_step1_naver(
        db, no_url, validator
    )
    print(f"  → 네이버 발견: {naver_found}개 / 검증 실패: {naver_rejected}개 / 잔여: {len(still_missing)}개")

    # ── 2단계: 카카오 (panel3 상세 API) ────────────────────────
    print(f"\n[ 2단계 ] 카카오 panel3 상세 API → homepages 추출 ({len(still_missing)}개 대상)")
    print("-" * 60)
    kakao_found, kakao_rejected = await run_step2_kakao(
        db, still_missing, validator
    )
    print(f"  → 카카오 발견: {kakao_found}개 / 검증 실패: {kakao_rejected}개")

    # ── 최종 리포트 ────────────────────────────────────────────
    total_found = naver_found + kakao_found
    total_rejected = naver_rejected + kakao_rejected
    total_with_url = len(with_url) + total_found
    total = len(hospitals)
    remaining = total - total_with_url
    hit_rate = (total_found / len(no_url) * 100) if no_url else 0.0

    print("\n" + "=" * 60)
    print("최종 리포트")
    print("=" * 60)
    print(f"  ┌─────────────────────────────────────────┐")
    print(f"  │ 소스별 발견 수                          │")
    print(f"  ├─────────────────────────────────────────┤")
    print(f"  │ 기존 URL (심평원 등):  {len(with_url):>5}개           │")
    print(f"  │ 네이버 보강:          +{naver_found:>4}개           │")
    print(f"  │ 카카오 보강:          +{kakao_found:>4}개           │")
    print(f"  ├─────────────────────────────────────────┤")
    print(f"  │ 검증 거부 (총):        {total_rejected:>5}개           │")
    print(f"  │   - 네이버 검증 실패:  {naver_rejected:>5}개           │")
    print(f"  │   - 카카오 검증 실패:  {kakao_rejected:>5}개           │")
    print(f"  ├─────────────────────────────────────────┤")
    print(f"  │ 히트율 (보강 대상 중): {hit_rate:>6.1f}%          │")
    print(f"  │ 크롤링 가능 (총):     {total_with_url:>5}개 / {total}개  │")
    print(f"  │ 잔여 (URL 없음):      {remaining:>5}개           │")
    print(f"  └─────────────────────────────────────────┘")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
