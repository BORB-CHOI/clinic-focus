"""실제 병원 사이트 크롤링 테스트 — 성북구 병원 3개."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from be.scripts._utils import load_env
load_env()

import httpx
from be.core.crawler import crawl_one_hospital

TEST_HOSPITALS = [
    {"id": "h_test_01", "name": "고려대학교 안암병원", "url": "http://anam.kumc.or.kr/main/index.do"},
    {"id": "h_test_02", "name": "서울척병원", "url": "http://www.chukhospital.com"},
    {"id": "h_test_03", "name": "성가복지병원", "url": "http://www.sgbokji.or.kr"},
]


async def main():
    print("=" * 60)
    print("실제 병원 사이트 크롤링 테스트")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        for hospital in TEST_HOSPITALS:
            print(f"\n{'─' * 60}")
            print(f"병원: {hospital['name']}")
            print(f"URL: {hospital['url']}")
            print(f"{'─' * 60}")

            try:
                result = await crawl_one_hospital(
                    hospital["id"],
                    hospital["url"],
                    client,
                )

                print(f"  크롤링 결과:")
                print(f"    페이지 수: {len(result.pages)}")
                print(f"    이미지 수: {len(result.images)}")

                for page in result.pages:
                    text_preview = page.html_text[:150].replace("\n", " ")
                    print(f"    [{page.page_type}] {len(page.html_text)}자 - {text_preview}...")

            except Exception as e:
                print(f"  ERROR: {e}")

            print()


if __name__ == "__main__":
    asyncio.run(main())
