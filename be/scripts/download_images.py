"""크롤링 결과에서 이미지 URL을 읽어 실제 이미지 파일 다운로드.

Vision 분석(비성님 파트)에 필요한 이미지 원본 수집.
크롤링 완료 후 실행.
"""

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

import httpx

from be.adapters.s3_adapter import S3Adapter

# 이미지 저장 경로
IMAGE_DIR = os.environ.get("IMAGE_DATA_DIR", os.path.expanduser("~/clinic-focus/data/images"))

# 허용 확장자
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}

# 최소 파일 크기 (아이콘 필터링, 1KB 미만 스킵)
MIN_FILE_SIZE = 1024

# 병원당 최대 이미지 수
MAX_IMAGES_PER_HOSPITAL = 20

# 동시 다운로드 수
CONCURRENCY = 5

USER_AGENT = "ClinicFocusBot/1.0 (research; contact@clinicfocus.kr)"


async def download_one_image(
    client: httpx.AsyncClient,
    image_url: str,
    save_path: str,
) -> bool:
    """이미지 1개 다운로드. 성공 시 True."""
    try:
        resp = await client.get(
            image_url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=10.0,
        )
        if resp.status_code != 200:
            return False

        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and "svg" not in content_type:
            return False

        data = resp.content
        if len(data) < MIN_FILE_SIZE:
            return False

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "wb") as f:
            f.write(data)
        return True

    except Exception:
        return False


def _get_filename_from_url(url: str, index: int) -> str:
    """URL에서 파일명 추출. 없으면 인덱스 기반 생성."""
    parsed = urlparse(url)
    path = parsed.path
    filename = os.path.basename(path)

    # 확장자 확인
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        filename = f"img_{index:03d}.jpg"

    # 파일명 길이 제한
    if len(filename) > 100:
        ext = os.path.splitext(filename)[1]
        filename = f"img_{index:03d}{ext}"

    return filename


async def process_hospital(
    client: httpx.AsyncClient,
    hospital_id: str,
    crawl_data,
    semaphore: asyncio.Semaphore,
) -> dict:
    """병원 1개의 이미지 전체 다운로드."""
    hospital_dir = os.path.join(IMAGE_DIR, hospital_id)

    # 이미 다운로드된 이미지 있으면 스킵
    if os.path.exists(hospital_dir) and len(os.listdir(hospital_dir)) > 0:
        return {"hospital_id": hospital_id, "downloaded": 0, "skipped": True}

    images = crawl_data.images[:MAX_IMAGES_PER_HOSPITAL]
    downloaded = 0

    for i, img in enumerate(images):
        # 확장자 필터
        ext = os.path.splitext(urlparse(img.url).path)[1].lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            continue

        filename = _get_filename_from_url(img.url, i)
        save_path = os.path.join(hospital_dir, filename)

        async with semaphore:
            success = await download_one_image(client, img.url, save_path)
            if success:
                downloaded += 1

        await asyncio.sleep(0.1)  # 예의상 딜레이

    return {"hospital_id": hospital_id, "downloaded": downloaded, "skipped": False}


async def main():
    s3 = S3Adapter()
    os.makedirs(IMAGE_DIR, exist_ok=True)

    print("=" * 60)
    print("이미지 다운로드 — 크롤링 결과 기반")
    print(f"저장 경로: {IMAGE_DIR}")
    print("=" * 60)

    # 크롤링 데이터 디렉토리에서 JSON 파일 목록
    crawl_dir = os.environ.get("CRAWL_DATA_DIR", os.path.expanduser("~/clinic-focus/data/crawl"))
    if not os.path.exists(crawl_dir):
        print("❌ 크롤링 데이터가 없습니다. crawl_all.py를 먼저 실행하세요.")
        return

    json_files = [f for f in os.listdir(crawl_dir) if f.endswith(".json")]
    print(f"  크롤링된 병원 수: {len(json_files)}개")

    if not json_files:
        print("❌ 크롤링 데이터가 없습니다.")
        return

    # 이미지 있는 병원만 필터
    targets = []
    for filename in json_files:
        hospital_id = filename.replace(".json", "")
        crawl_data = s3.load_crawl_data(hospital_id)
        if crawl_data and len(crawl_data.images) > 0:
            targets.append((hospital_id, crawl_data))

    print(f"  이미지 있는 병원: {len(targets)}개")
    total_images = sum(len(cd.images) for _, cd in targets)
    print(f"  총 이미지 URL: {total_images}개")
    print("-" * 60)

    # 다운로드 실행
    semaphore = asyncio.Semaphore(CONCURRENCY)
    total_downloaded = 0
    total_skipped = 0

    async with httpx.AsyncClient() as client:
        for i, (hospital_id, crawl_data) in enumerate(targets, 1):
            result = await process_hospital(client, hospital_id, crawl_data, semaphore)

            if result["skipped"]:
                total_skipped += 1
            else:
                total_downloaded += result["downloaded"]

            if i % 10 == 0:
                print(f"  [{i}/{len(targets)}] 진행 중... (다운로드: {total_downloaded}개)")

    print("\n" + "=" * 60)
    print("이미지 다운로드 완료!")
    print(f"  ✅ 다운로드: {total_downloaded}개")
    print(f"  ⏭️ 스킵 (이미 있음): {total_skipped}개")
    print(f"  📁 저장 경로: {IMAGE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
