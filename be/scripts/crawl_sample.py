"""50개 병원 샘플 크롤링 — 검증용.

다양한 유형(한의원, 피부과, 치과, 성형외과, 내과 등)이 섞이도록
DynamoDB에서 URL 있는 병원 50개를 선택하여 크롤링한다.
결과는 S3에 저장되며, 진행률/ETA를 터미널에 출력한다.
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout.reconfigure(line_buffering=True)

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import httpx

from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter
from be.core.browser_manager import BrowserManager
from be.core.crawler import crawl_one_hospital

SAMPLE_SIZE = 50


async def main():
    db = DynamoAdapter()
    s3 = S3Adapter()

    print("=" * 60)
    print(f"샘플 크롤링 — {SAMPLE_SIZE}개 병원 (검증용)")
    print("=" * 60)

    # 강남구 병원 중 URL 있는 것만 조회
    print("\nDynamoDB에서 강남구 병원 조회 중...")
    hospitals = db.list_hospitals_by_sigungu("강남구")
    with_url = [
        h for h in hospitals
        if h.contact.website_url
        and h.contact.website_url.startswith("http")
    ]
    print(f"  URL 있는 병원: {len(with_url)}개")

    # 이미 크롤링된 병원 제외, 다양한 유형 선택 (유형별 최대 8개)
    from collections import defaultdict
    type_buckets = defaultdict(list)
    MAX_PER_TYPE = 8

    for h in with_url:
        # 이미 크롤링된 건 스킵
        existing = s3.load_crawl_data(h.hospital_id)
        if existing and len(existing.pages) > 0:
            continue

        # 병원 유형 분류 (이름 기반)
        name = h.name
        h_type = "기타"
        if "피부" in name:
            h_type = "피부과"
        elif "치과" in name:
            h_type = "치과"
        elif "한의" in name or "한방" in name:
            h_type = "한의원"
        elif "성형" in name:
            h_type = "성형외과"
        elif "내과" in name:
            h_type = "내과"
        elif "정형" in name:
            h_type = "정형외과"
        elif "안과" in name:
            h_type = "안과"
        elif "이비인후" in name:
            h_type = "이비인후과"
        elif "산부인과" in name or "여성" in name:
            h_type = "산부인과"
        elif "정신" in name:
            h_type = "정신과"

        if len(type_buckets[h_type]) < MAX_PER_TYPE:
            type_buckets[h_type].append({"hospital": h, "type": h_type})

    # 각 유형에서 골고루 뽑기
    targets = []
    for h_type, items in type_buckets.items():
        targets.extend(items)
        if len(targets) >= SAMPLE_SIZE:
            break
    targets = targets[:SAMPLE_SIZE]

    print(f"  크롤링 대상: {len(targets)}개")

    # 유형별 분포 출력
    from collections import Counter
    type_dist = Counter(t["type"] for t in targets)
    print(f"  유형 분포: {dict(type_dist)}")
    print("-" * 60)

    # 크롤링 실행
    results = {"static_success": 0, "js_render_success": 0, "failed": 0}
    start_time = time.time()

    async with BrowserManager() as bm:
        async with httpx.AsyncClient() as client:
            for i, item in enumerate(targets, 1):
                hospital = item["hospital"]
                name = hospital.name
                url = hospital.contact.website_url

                try:
                    crawl_data = await crawl_one_hospital(
                        hospital.hospital_id, url, client, browser_manager=bm
                    )

                    if not crawl_data.pages:
                        results["failed"] += 1
                        print(f"  [{i}/{len(targets)}] ❌ {name} — 실패 (빈 결과)")
                        continue

                    main_page = next(
                        (p for p in crawl_data.pages if p.page_type == "main"), None
                    )
                    total_pages = len(crawl_data.pages)
                    total_images = len(crawl_data.images)

                    if main_page and main_page.render_method == "playwright":
                        results["js_render_success"] += 1
                        s3.save_crawl_data(hospital.hospital_id, crawl_data)
                        print(
                            f"  [{i}/{len(targets)}] 🔄 {name} — JS렌더링, "
                            f"{total_pages}p, {total_images}img, {len(main_page.html_text)}자"
                        )
                    else:
                        results["static_success"] += 1
                        s3.save_crawl_data(hospital.hospital_id, crawl_data)
                        print(
                            f"  [{i}/{len(targets)}] ✅ {name} — 정적, "
                            f"{total_pages}p, {total_images}img, {len(main_page.html_text) if main_page else 0}자"
                        )

                except Exception as e:
                    results["failed"] += 1
                    print(f"  [{i}/{len(targets)}] ❌ {name} — {type(e).__name__}: {e}")

                # 진행률 + ETA (10개마다)
                if i % 10 == 0:
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

                await asyncio.sleep(0.5)

    # 최종 리포트
    elapsed = time.time() - start_time
    success_count = results["static_success"] + results["js_render_success"]
    total = success_count + results["failed"]
    success_rate = success_count / total * 100 if total else 0

    print("\n" + "=" * 60)
    print("샘플 크롤링 완료!")
    print("=" * 60)
    print(f"  ✅ 정적 성공: {results['static_success']}개")
    print(f"  🔄 JS 렌더링 성공: {results['js_render_success']}개")
    print(f"  ❌ 실패: {results['failed']}개")
    print(f"  ─────────────────")
    print(f"  성공률: {success_rate:.1f}% ({success_count}/{total})")
    print(f"  소요 시간: {elapsed:.0f}초 ({elapsed/60:.1f}분)")
    print(f"  저장 위치: S3 crawl/{{hospital_id}}/crawl_data.json")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
