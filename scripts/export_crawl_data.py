"""성공한 병원들의 CrawlData를 JSON으로 저장 — 최비성 AI 분류 테스트용."""
import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

import httpx
from be.adapters.hira_adapter import HiraAdapter
from be.core.crawler import crawl_one_hospital

MIN_TEXT_THRESHOLD = 100


async def main():
    hira = HiraAdapter()

    print("심평원 API 조회 중...")
    raw_hospitals = hira.get_hospitals_by_region(sido_code="110000", sigungu_code="110012")

    # 홈페이지 있는 병원 필터
    targets = []
    for h in raw_hospitals:
        url = h.get("hospUrl", "") or ""
        if url and (url.startswith("http://") or url.startswith("https://")):
            targets.append({
                "raw": h,
                "id": h.get("ykiho", ""),
                "name": h.get("yadmNm", ""),
                "url": url,
            })

    print(f"크롤링 대상: {len(targets)}개")
    print("크롤링 + 심평원 데이터 병합 중...\n")

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "crawl_results"
    )
    os.makedirs(output_dir, exist_ok=True)

    success_count = 0

    async with httpx.AsyncClient() as client:
        for i, hospital in enumerate(targets, 1):
            print(f"[{i:2d}/{len(targets)}] {hospital['name']} ... ", end="", flush=True)

            try:
                crawl_data = await crawl_one_hospital(
                    hospital["id"],
                    hospital["url"],
                    client,
                )

                # 메인 페이지 텍스트 길이 체크
                main_text_len = 0
                if crawl_data.pages:
                    main_page = next((p for p in crawl_data.pages if p.page_type == "main"), None)
                    if main_page:
                        main_text_len = len(main_page.html_text)

                if main_text_len < MIN_TEXT_THRESHOLD:
                    print("⚠️ 스킵 (JS 렌더링 필요)")
                    await asyncio.sleep(0.5)
                    continue

                # 심평원 공공 데이터 병합
                raw = hospital["raw"]
                from shared.models import PublicData
                crawl_data.public_data = PublicData(
                    license_number=hospital["id"],
                    name=raw.get("yadmNm", ""),
                    address=raw.get("addr", ""),
                    phone=raw.get("telno", ""),
                    lat=float(raw.get("YPos", 0) or 0),
                    lng=float(raw.get("XPos", 0) or 0),
                    specialists=[raw.get("dgsbjtCdNm", "")] if raw.get("dgsbjtCdNm") else [],
                    registered_devices=[],
                )

                # JSON 저장
                filename = f"{hospital['id']}.json"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(crawl_data.model_dump_json(indent=2))

                total_text = sum(len(p.html_text) for p in crawl_data.pages)
                print(f"✅ 저장 ({len(crawl_data.pages)}페이지, {total_text}자)")
                success_count += 1

            except Exception as e:
                print(f"❌ 에러: {e}")

            await asyncio.sleep(0.5)

    print(f"\n{'=' * 60}")
    print(f"완료! {success_count}개 병원 CrawlData 저장됨")
    print(f"저장 위치: {output_dir}")
    print(f"{'=' * 60}")
    print(f"\n최비성한테 data/crawl_results/ 폴더를 공유하면 됨.")
    print(f"각 JSON 파일이 shared/models.py의 CrawlData 형태.")


if __name__ == "__main__":
    asyncio.run(main())
