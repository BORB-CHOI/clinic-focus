"""DynamoDB에 저장된 병원 중 홈페이지 URL 있는 병원 전체 크롤링.

크롤링 결과는 로컬 파일시스템에 JSON으로 저장.
BrowserManager를 통합하여 JS 렌더링 필요 사이트를 자동으로 Playwright 폴백 처리.
"""

import asyncio
import os
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import httpx

from be.adapters.s3_adapter import S3Adapter
from be.core.browser_manager import BrowserManager
from be.core.crawler import crawl_one_hospital

# 텍스트 100자 미만이면 JS 렌더링 필요로 판단
MIN_TEXT_THRESHOLD = 100


async def main():
    s3 = S3Adapter()

    print("=" * 60)
    print("전체 크롤링 — 홈페이지 URL 있는 병원")
    print("=" * 60)

    # DynamoDB에서 URL 있는 병원 조회 (DynamoAdapter 사용)
    from be.adapters.dynamo_adapter import DynamoAdapter
    db = DynamoAdapter()
    print("\nDynamoDB에서 강남구 병원 조회 중...")
    hospitals = db.list_hospitals_by_sigungu("강남구")

    # URL 있는 병원 필터
    targets = []
    for h in hospitals:
        url = h.contact.website_url
        if url and url.startswith("http"):
            targets.append({
                "hospital_id": h.hospital_id,
                "name": h.name,
                "url": url,
            })

    print(f"  전체 병원: {len(hospitals)}개")
    print(f"  크롤링 대상 (URL 있음): {len(targets)}개")
    print("-" * 60)

    results = {"static_success": 0, "js_render_success": 0, "failed": 0}
    start_time = time.time()

    async with BrowserManager() as bm:
        async with httpx.AsyncClient() as client:
            for i, hospital in enumerate(targets, 1):
                hospital_id = hospital["hospital_id"]
                name = hospital["name"]
                url = hospital["url"]

                # 이미 크롤링된 파일 있으면 스킵 (기존 데이터의 render_method 확인)
                existing = s3.load_crawl_data(hospital_id)
                if existing and len(existing.pages) > 0:
                    main_page = next(
                        (p for p in existing.pages if p.page_type == "main"), None
                    )
                    if main_page and main_page.render_method == "playwright":
                        results["js_render_success"] += 1
                    else:
                        results["static_success"] += 1
                    continue

                try:
                    crawl_data = await crawl_one_hospital(
                        hospital_id, url, client, browser_manager=bm
                    )

                    if not crawl_data.pages:
                        results["failed"] += 1
                        print(f"  [{i}/{len(targets)}] ❌ {name} — 크롤링 실패 (빈 결과)")
                        continue

                    main_page = next(
                        (p for p in crawl_data.pages if p.page_type == "main"), None
                    )
                    total_pages = len(crawl_data.pages)
                    total_images = len(crawl_data.images)

                    if main_page and main_page.render_method == "playwright":
                        results["js_render_success"] += 1
                        s3.save_crawl_data(hospital_id, crawl_data)
                        print(
                            f"  [{i}/{len(targets)}] 🔄 {name} — JS 렌더링 성공, "
                            f"{total_pages}페이지, {total_images}이미지"
                        )
                    else:
                        results["static_success"] += 1
                        s3.save_crawl_data(hospital_id, crawl_data)
                        print(
                            f"  [{i}/{len(targets)}] ✅ {name} — 정적 크롤링 성공, "
                            f"{total_pages}페이지, {total_images}이미지"
                        )

                except Exception as e:
                    results["failed"] += 1
                    print(f"  [{i}/{len(targets)}] ❌ {name} — {e}")

                # 예의상 딜레이
                await asyncio.sleep(0.5)

                # 50개마다 진행률 + ETA 출력
                if i % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    remaining = len(targets) - i
                    eta_sec = remaining / rate if rate > 0 else 0
                    eta_min = int(eta_sec // 60)
                    eta_s = int(eta_sec % 60)
                    success = results["static_success"] + results["js_render_success"]
                    print(
                        f"\n  📊 [{i}/{len(targets)}] {i/len(targets)*100:.0f}% | "
                        f"성공: {success} | 실패: {results['failed']} | "
                        f"속도: {rate:.2f}건/초 | ETA: {eta_min}분 {eta_s}초\n"
                    )

    # 크롤링 리포트 출력
    total_processed = results["static_success"] + results["js_render_success"] + results["failed"]
    success_count = results["static_success"] + results["js_render_success"]
    success_rate = success_count / total_processed * 100 if total_processed else 0

    print("\n" + "=" * 60)
    print("크롤링 완료!")
    print("-" * 60)
    print(f"  ✅ 정적 크롤링 성공: {results['static_success']}개")
    print(f"  🔄 JS 렌더링 성공: {results['js_render_success']}개")
    print(f"  ❌ 실패: {results['failed']}개")
    print("-" * 60)
    print(f"  총 처리: {total_processed}개")
    print(f"  성공률: {success_rate:.1f}% ({success_count}/{total_processed})")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
