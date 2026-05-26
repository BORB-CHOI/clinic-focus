"""이미지 다운로드 로직 로컬 테스트.

실제 병원 사이트에서 이미지 URL 몇 개를 수집하고 다운로드해본다.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import httpx
from be.core.crawler import crawl_one_hospital
from be.scripts.download_images import download_one_image, _get_filename_from_url

# 테스트용 저장 경로
TEST_IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "test_images")


async def main():
    print("=" * 60)
    print("이미지 다운로드 로컬 테스트")
    print(f"저장 경로: {TEST_IMAGE_DIR}")
    print("=" * 60)

    # 1. 살아있는 병원 사이트 크롤링해서 이미지 URL 수집
    test_url = "https://gs.severance.healthcare/gs"  # 강남세브란스 (네이버에서 확인)
    print(f"\n[1] 크롤링: {test_url}")

    async with httpx.AsyncClient() as client:
        crawl_data = await crawl_one_hospital("test_severance", test_url, client)

    print(f"  페이지: {len(crawl_data.pages)}개")
    print(f"  이미지 URL: {len(crawl_data.images)}개")

    if not crawl_data.images:
        print("  ❌ 이미지 없음. 다른 사이트로 시도...")
        # 대안: 직접 이미지 URL로 테스트
        test_images = [
            "https://via.placeholder.com/300x200.jpg",
            "https://via.placeholder.com/500x400.png",
        ]
    else:
        test_images = [img.url for img in crawl_data.images[:5]]
        print(f"  상위 5개 이미지 URL:")
        for url in test_images:
            print(f"    {url}")

    # 2. 이미지 다운로드 테스트
    print(f"\n[2] 이미지 다운로드 테스트 ({len(test_images)}개)")
    os.makedirs(TEST_IMAGE_DIR, exist_ok=True)

    downloaded = 0
    async with httpx.AsyncClient() as client:
        for i, img_url in enumerate(test_images):
            filename = _get_filename_from_url(img_url, i)
            save_path = os.path.join(TEST_IMAGE_DIR, filename)

            success = await download_one_image(client, img_url, save_path)
            if success:
                file_size = os.path.getsize(save_path)
                print(f"  ✅ {filename} ({file_size:,} bytes)")
                downloaded += 1
            else:
                print(f"  ❌ {filename} — 다운로드 실패")

    print(f"\n[3] 결과: {downloaded}/{len(test_images)} 다운로드 성공")
    print(f"  저장 위치: {TEST_IMAGE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
