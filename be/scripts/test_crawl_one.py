"""홈페이지 URL 있는 병원 1개 크롤링 테스트."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import httpx
from be.adapters.dynamo_adapter import DynamoAdapter
from be.adapters.s3_adapter import S3Adapter
from be.core.crawler import crawl_one_hospital


async def main():
    db = DynamoAdapter()
    s3 = S3Adapter()

    print("=" * 60)
    print("크롤링 테스트 — 홈페이지 있는 병원 1개")
    print("=" * 60)

    # DynamoDB에서 홈페이지 URL 있는 병원 찾기
    # scan으로 전체 조회 후 website_url 있는 것 필터
    import boto3
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table("Hospitals")

    resp = table.scan(Limit=100)
    items = resp.get("Items", [])

    target = None
    for item in items:
        contact = item.get("contact", {})
        url = contact.get("website_url")
        if url and url.startswith("http"):
            target = item
            break

    if not target:
        print("❌ 홈페이지 URL 있는 병원을 찾지 못했습니다.")
        return

    hospital_id = target["hospital_id"]
    name = target["name"]
    website_url = target["contact"]["website_url"]

    print(f"\n대상 병원: {name}")
    print(f"ID: {hospital_id}")
    print(f"URL: {website_url}")
    print("-" * 60)

    # 크롤링 실행
    print("\n크롤링 중...")
    async with httpx.AsyncClient() as client:
        crawl_data = await crawl_one_hospital(hospital_id, website_url, client)

    print(f"\n크롤링 결과:")
    print(f"  페이지 수: {len(crawl_data.pages)}")
    print(f"  이미지 수: {len(crawl_data.images)}")

    for page in crawl_data.pages:
        text_preview = page.html_text[:100] + "..." if len(page.html_text) > 100 else page.html_text
        print(f"  [{page.page_type}] {page.url}")
        print(f"    텍스트 길이: {len(page.html_text)}자")
        print(f"    미리보기: {text_preview}")
        print()

    # 로컬에 저장
    path = s3.save_crawl_data(hospital_id, crawl_data)
    print(f"\n💾 저장 완료: {path}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
