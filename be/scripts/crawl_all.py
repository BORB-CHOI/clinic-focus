"""DynamoDB에 저장된 병원 중 홈페이지 URL 있는 병원 전체 크롤링.

크롤링 결과는 로컬 파일시스템에 JSON으로 저장.
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import boto3
import httpx

from be.adapters.s3_adapter import S3Adapter
from be.core.crawler import crawl_one_hospital

# 텍스트 100자 미만이면 JS 렌더링 필요로 판단
MIN_TEXT_THRESHOLD = 100


async def main():
    s3 = S3Adapter()

    print("=" * 60)
    print("전체 크롤링 — 홈페이지 URL 있는 병원")
    print("=" * 60)

    # DynamoDB에서 URL 있는 병원 조회
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table("Hospitals")

    all_items = []
    resp = table.scan()
    all_items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        all_items.extend(resp.get("Items", []))

    # URL 있는 병원 필터
    targets = []
    for item in all_items:
        contact = item.get("contact", {})
        url = contact.get("website_url")
        if url and (url.startswith("http://") or url.startswith("https://")):
            targets.append({
                "hospital_id": item["hospital_id"],
                "name": item.get("name", ""),
                "url": url,
            })

    print(f"  전체 병원: {len(all_items)}개")
    print(f"  크롤링 대상 (URL 있음): {len(targets)}개")
    print("-" * 60)

    results = {"success": 0, "js_needed": 0, "failed": 0}

    async with httpx.AsyncClient() as client:
        for i, hospital in enumerate(targets, 1):
            hospital_id = hospital["hospital_id"]
            name = hospital["name"]
            url = hospital["url"]

            # 이미 크롤링된 파일 있으면 스킵
            existing = s3.load_crawl_data(hospital_id)
            if existing and len(existing.pages) > 0:
                results["success"] += 1
                continue

            try:
                crawl_data = await crawl_one_hospital(hospital_id, url, client)

                main_page = next((p for p in crawl_data.pages if p.page_type == "main"), None)
                main_text_len = len(main_page.html_text) if main_page else 0
                total_pages = len(crawl_data.pages)
                total_images = len(crawl_data.images)

                if main_text_len >= MIN_TEXT_THRESHOLD:
                    s3.save_crawl_data(hospital_id, crawl_data)
                    results["success"] += 1
                    if i % 10 == 0:
                        print(f"  [{i}/{len(targets)}] ✅ {name} — {total_pages}페이지, {total_images}이미지")
                else:
                    results["js_needed"] += 1
                    if i % 10 == 0:
                        print(f"  [{i}/{len(targets)}] ⚠️ {name} — JS 렌더링 필요 ({main_text_len}자)")

            except Exception as e:
                results["failed"] += 1
                if i % 10 == 0:
                    print(f"  [{i}/{len(targets)}] ❌ {name} — {e}")

            # 예의상 딜레이
            await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print("크롤링 완료!")
    print(f"  ✅ 성공: {results['success']}개")
    print(f"  ⚠️ JS 렌더링 필요: {results['js_needed']}개")
    print(f"  ❌ 실패: {results['failed']}개")
    success_rate = results["success"] / len(targets) * 100 if targets else 0
    print(f"  성공률: {success_rate:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
