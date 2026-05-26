"""be/scripts/crawl_all.py 의 AI 트랙 우회 사본.

본체와의 차이는 단 한 줄 — Hospitals 테이블 참조에 TABLE_PREFIX 적용.
이슈 #23 머지되면 본체로 갈아타고 이 파일은 삭제.

실행:
    .venv/bin/python ai/scratch/crawl_all_ai.py
"""

import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from be.scripts._utils import load_env  # noqa: E402

load_env()

import boto3  # noqa: E402
import httpx  # noqa: E402

from be.adapters.s3_adapter import S3Adapter  # noqa: E402
from be.core.crawler import crawl_one_hospital  # noqa: E402

MIN_TEXT_THRESHOLD = 100
TABLE_PREFIX = os.environ.get("TABLE_PREFIX", "")


async def main():
    s3 = S3Adapter()

    print("=" * 60)
    print("AI 트랙 e2e 크롤링 — TABLE_PREFIX 적용 사본")
    print("=" * 60)

    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table(f"{TABLE_PREFIX}Hospitals")

    all_items = []
    resp = table.scan()
    all_items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        all_items.extend(resp.get("Items", []))

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
                    print(f"  [{i}/{len(targets)}] ✅ {name} — {total_pages}페이지, {total_images}이미지")
                else:
                    results["js_needed"] += 1
                    print(f"  [{i}/{len(targets)}] ⚠️ {name} — JS 렌더링 필요 ({main_text_len}자)")

            except Exception as e:
                results["failed"] += 1
                print(f"  [{i}/{len(targets)}] ❌ {name} — {e}")

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
