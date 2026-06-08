"""E2E 스모크 테스트 — 5개 병원으로 enrich → crawl 전체 흐름 확인.

수동 실행 스크립트. DynamoDB 및 네트워크 접근이 필요하므로 자동화 테스트가 아닌
수동 검증용으로 사용.

실행:
    python -m be.scripts.smoke_test

확인 사항:
    1. URL 없는 병원 → enrich (네이버 검색) → URL 발견 여부
    2. URL 있는 병원 → crawl → 정적/JS 렌더링 결과 확인
    3. 전체 파이프라인 흐름이 에러 없이 완료되는지 확인
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import boto3
import httpx

from be.adapters.s3_adapter import S3Adapter
from be.core.browser_manager import BrowserManager
from be.core.crawler import crawl_one_hospital
from be.core.url_validator import URLValidator


# 스모크 테스트 대상 병원 수
SMOKE_TEST_LIMIT = 5


async def smoke_enrich(hospitals_no_url: list[dict]) -> list[dict]:
    """URL 없는 병원 중 최대 5개에 대해 네이버 검색으로 URL 보강 시도."""
    from be.adapters.naver_map_adapter import NaverMapAdapter

    naver_key = os.environ.get("NAVER_MAP_CLIENT_ID", "")
    if not naver_key:
        print("  ⚠️  NAVER_MAP_CLIENT_ID 미설정 — enrich 단계 건너뜀")
        return []

    naver = NaverMapAdapter()
    validator = URLValidator()
    enriched = []

    targets = hospitals_no_url[:SMOKE_TEST_LIMIT]
    print(f"\n{'─' * 50}")
    print(f"[Enrich] URL 없는 병원 {len(targets)}개 보강 시도")
    print(f"{'─' * 50}")

    for i, h in enumerate(targets, 1):
        name = h["name"]
        address = h.get("address", "")
        result = naver.search_hospital_multi_query(name, address)
        link = (result or {}).get("link", "")

        if link and link.startswith("http"):
            validated = await validator.validate(link)
            if validated:
                print(f"  [{i}/{len(targets)}] ✅ {name} → {validated}")
                enriched.append({"hospital_id": h["hospital_id"], "name": name, "url": validated})
            else:
                print(f"  [{i}/{len(targets)}] ⚠️ {name} — URL 검증 실패: {link}")
        else:
            print(f"  [{i}/{len(targets)}] ❌ {name} — URL 미발견")

    return enriched


async def smoke_crawl(hospitals_with_url: list[dict]) -> dict:
    """URL 있는 병원 중 최대 5개에 대해 크롤링 수행."""
    targets = hospitals_with_url[:SMOKE_TEST_LIMIT]
    results = {"static_success": 0, "js_render_success": 0, "failed": 0}

    print(f"\n{'─' * 50}")
    print(f"[Crawl] URL 있는 병원 {len(targets)}개 크롤링")
    print(f"{'─' * 50}")

    async with BrowserManager() as bm:
        async with httpx.AsyncClient() as client:
            for i, h in enumerate(targets, 1):
                hospital_id = h["hospital_id"]
                name = h["name"]
                url = h["url"]

                try:
                    crawl_data = await crawl_one_hospital(
                        hospital_id, url, client, browser_manager=bm
                    )

                    if not crawl_data.pages:
                        results["failed"] += 1
                        print(f"  [{i}/{len(targets)}] ❌ {name} — 빈 결과")
                        continue

                    main_page = next(
                        (p for p in crawl_data.pages if p.page_type == "main"), None
                    )
                    total_pages = len(crawl_data.pages)
                    render = main_page.render_method if main_page else "unknown"

                    if render == "playwright":
                        results["js_render_success"] += 1
                        print(
                            f"  [{i}/{len(targets)}] 🔄 {name} — JS 렌더링 성공, "
                            f"{total_pages}페이지, render={render}"
                        )
                    else:
                        results["static_success"] += 1
                        print(
                            f"  [{i}/{len(targets)}] ✅ {name} — 정적 성공, "
                            f"{total_pages}페이지, render={render}"
                        )

                except Exception as e:
                    results["failed"] += 1
                    print(f"  [{i}/{len(targets)}] ❌ {name} — {e}")

                await asyncio.sleep(0.5)

    return results


async def main() -> None:
    print("=" * 60)
    print("E2E 스모크 테스트 — 5개 병원 enrich → crawl 전체 흐름")
    print("=" * 60)

    # DynamoDB에서 병원 조회
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table("Hospitals")

    all_items = []
    resp = table.scan(Limit=100)  # 스모크 테스트이므로 100개만 스캔
    all_items.extend(resp.get("Items", []))

    # URL 있는 병원 / 없는 병원 분류
    with_url = []
    no_url = []
    for item in all_items:
        contact = item.get("contact", {})
        url = contact.get("website_url")
        hospital_info = {
            "hospital_id": item["hospital_id"],
            "name": item.get("name", ""),
            "address": item.get("location", {}).get("address", ""),
        }
        if url and (url.startswith("http://") or url.startswith("https://")):
            hospital_info["url"] = url
            with_url.append(hospital_info)
        else:
            no_url.append(hospital_info)

    print(f"\n  스캔된 병원: {len(all_items)}개")
    print(f"  URL 있음: {len(with_url)}개")
    print(f"  URL 없음: {len(no_url)}개")

    # ── Step 1: Enrich (URL 없는 병원 보강 시도) ──
    enriched = await smoke_enrich(no_url)

    # ── Step 2: Crawl (URL 있는 병원 크롤링) ──
    crawl_results = await smoke_crawl(with_url)

    # ── 최종 리포트 ──
    total_crawled = (
        crawl_results["static_success"]
        + crawl_results["js_render_success"]
        + crawl_results["failed"]
    )
    success_count = crawl_results["static_success"] + crawl_results["js_render_success"]
    success_rate = success_count / total_crawled * 100 if total_crawled else 0

    print(f"\n{'=' * 60}")
    print("스모크 테스트 결과")
    print(f"{'=' * 60}")
    print(f"\n  [Enrich 결과]")
    print(f"    시도: {min(len(no_url), SMOKE_TEST_LIMIT)}개")
    print(f"    성공: {len(enriched)}개")
    print(f"\n  [Crawl 결과]")
    print(f"    ✅ 정적 성공: {crawl_results['static_success']}개")
    print(f"    🔄 JS 렌더링 성공: {crawl_results['js_render_success']}개")
    print(f"    ❌ 실패: {crawl_results['failed']}개")
    print(f"    성공률: {success_rate:.1f}%")
    print(f"\n{'=' * 60}")

    # 전체 흐름 성공 여부 판정
    if crawl_results["failed"] <= crawl_results["static_success"] + crawl_results["js_render_success"]:
        print("✅ 스모크 테스트 PASS — 파이프라인 정상 동작")
    else:
        print("⚠️ 스모크 테스트 WARNING — 실패율이 높음, 확인 필요")


if __name__ == "__main__":
    asyncio.run(main())
