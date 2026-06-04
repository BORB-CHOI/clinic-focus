"""네이버 블로그 RSS 크롤링 — blog.naver.com URL 병원 대상.

RSS 피드(https://rss.blog.naver.com/{blog_id}.xml)로 최신 글 50개 수집.
Playwright 불필요, 단순 HTTP GET으로 3분 내 전체 완료.

결과는 S3에 기존 crawl_data.json과 동일 구조로 저장.
"""

import asyncio
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from datetime import datetime

import boto3
import httpx
from boto3.dynamodb.conditions import Key
from bs4 import BeautifulSoup

from be.adapters.s3_adapter import S3Adapter
from shared.models import CrawlData, CrawledImage, CrawledPage, PublicData


def extract_blog_id(url: str) -> str | None:
    """blog.naver.com URL에서 blog_id 추출."""
    match = re.search(r'blog\.naver\.com/([^/?#]+)', url)
    return match.group(1) if match else None


def parse_rss_feed(xml_text: str, blog_url: str) -> tuple[list[CrawledPage], list[CrawledImage]]:
    """RSS XML에서 CrawledPage 리스트 추출."""
    pages: list[CrawledPage] = []
    images: list[CrawledImage] = []

    # item 태그 추출
    items = re.findall(r'<item>(.*?)</item>', xml_text, re.DOTALL)

    for item_xml in items[:50]:  # 최대 50개
        # 제목
        title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item_xml)
        if not title_match:
            title_match = re.search(r'<title>(.*?)</title>', item_xml)
        title = title_match.group(1) if title_match else ""

        # 본문 (description)
        desc_match = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', item_xml, re.DOTALL)
        if not desc_match:
            desc_match = re.search(r'<description>(.*?)</description>', item_xml, re.DOTALL)
        
        if desc_match:
            desc_html = desc_match.group(1)
            # HTML에서 이미지 추출
            img_matches = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', desc_html)
            for img_url in img_matches[:5]:  # 글당 최대 5개
                if img_url.startswith('http') and 'blogfiles' in img_url:
                    images.append(CrawledImage(
                        url=img_url,
                        page_url=blog_url,
                        alt_text=title[:50] if title else None,
                    ))

            # HTML 태그 제거 → 텍스트
            soup = BeautifulSoup(desc_html, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)
        else:
            text = ""

        # 링크
        link_match = re.search(r'<link>(.*?)</link>', item_xml)
        post_url = link_match.group(1).strip() if link_match else blog_url

        full_text = f"{title} {text}".strip()
        if len(full_text) < 20:
            continue

        pages.append(CrawledPage(
            url=post_url,
            page_type="blog",
            html_text=full_text,
            fetched_at=datetime.utcnow(),
            render_method="static",
        ))

    return pages, images


async def crawl_blog_rss(blog_id: str, blog_url: str, client: httpx.AsyncClient) -> tuple[list[CrawledPage], list[CrawledImage]] | None:
    """RSS 피드로 블로그 글 수집."""
    rss_url = f"https://rss.blog.naver.com/{blog_id}.xml"
    try:
        resp = await client.get(rss_url, timeout=10.0)
        if resp.status_code != 200:
            return None
        return parse_rss_feed(resp.text, blog_url)
    except Exception:
        return None


async def main():
    s3 = S3Adapter()

    print("=" * 60)
    print("네이버 블로그 RSS 크롤링")
    print("=" * 60)

    # DynamoDB에서 blog.naver.com URL 병원 조회
    dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    table = dynamodb.Table("kmuproj-02-team3-backend")

    blog_hospitals = []
    kwargs = {
        "IndexName": "sigungu-index",
        "KeyConditionExpression": Key("sigungu").eq("강남구"),
    }

    resp = table.query(**kwargs)
    items = resp.get("Items", [])
    while True:
        for item in items:
            contact = item.get("contact") or {}
            url = contact.get("website_url") or ""
            if "blog.naver.com" in url:
                blog_id = extract_blog_id(url)
                if blog_id:
                    blog_hospitals.append({
                        "hospital_id": item["hospital_id"],
                        "name": item.get("name", ""),
                        "blog_id": blog_id,
                        "url": url,
                    })
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        resp = table.query(**kwargs)
        items = resp.get("Items", [])

    print(f"  블로그 URL 병원: {len(blog_hospitals)}개")
    print("-" * 60)

    success = 0
    failed = 0
    skipped = 0
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        for i, hospital in enumerate(blog_hospitals, 1):
            hospital_id = hospital["hospital_id"]
            blog_id = hospital["blog_id"]
            name = hospital["name"]
            url = hospital["url"]

            # 이미 S3에 있고 pages > 0이면 스킵
            existing = s3.load_crawl_data(hospital_id)
            if existing and len(existing.pages) > 0:
                skipped += 1
                continue

            # RSS 크롤링
            result = await crawl_blog_rss(blog_id, url, client)

            if result is None or len(result[0]) == 0:
                failed += 1
                if i % 50 == 0:
                    print(f"  [{i}/{len(blog_hospitals)}] 진행중... 성공: {success}, 실패: {failed}, 스킵: {skipped}")
                continue

            pages, images = result

            # CrawlData 생성 + S3 저장
            crawl_data = CrawlData(
                hospital_id=hospital_id,
                website_url=url,
                pages=pages,
                images=images[:30],
                public_data=PublicData(license_number="", specialists=[], registered_devices=[]),
            )

            s3.save_crawl_data(hospital_id, crawl_data)
            success += 1
            print(f"  [{i}/{len(blog_hospitals)}] ✅ {name} — {len(pages)}글, {len(images)}이미지")

            # 속도 제한
            await asyncio.sleep(0.3)

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("블로그 RSS 크롤링 완료!")
    print("-" * 60)
    print(f"  ✅ 성공: {success}개")
    print(f"  ❌ 실패: {failed}개")
    print(f"  ⏭️ 스킵 (이미 있음): {skipped}개")
    print(f"  ⏱️ 소요 시간: {elapsed:.0f}초")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
