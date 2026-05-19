"""성북구 홈페이지 있는 병원 62개 전체 크롤링 + 통계."""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from be.scripts._utils import load_env, PROJECT_ROOT
load_env()

import httpx
from be.adapters.hira_adapter import HiraAdapter
from be.core.crawler import crawl_one_hospital
from shared.region_codes import SEOUL_SIDO_CODE, SEOUL_SIGUNGU_CODES

# 텍스트 100자 미만이면 JS 렌더링 필요로 판단
MIN_TEXT_THRESHOLD = 100


async def main():
    hira = HiraAdapter()

    print("=" * 60)
    print("성북구 전체 크롤링 테스트")
    print("=" * 60)

    print("\n심평원 API 조회 중...")
    raw_hospitals = hira.get_hospitals_by_region(
        sido_code=SEOUL_SIDO_CODE, sigungu_code=SEOUL_SIGUNGU_CODES["성북구"]
    )

    targets = []
    for h in raw_hospitals:
        url = h.get("hospUrl", "") or ""
        if url and (url.startswith("http://") or url.startswith("https://")):
            targets.append({
                "id": h.get("ykiho", ""),
                "name": h.get("yadmNm", ""),
                "url": url,
                "specialty": h.get("dgsbjtCdNm", ""),
            })

    print(f"크롤링 대상: {len(targets)}개")
    print("-" * 60)

    results = {"success": [], "js_needed": [], "failed": []}

    async with httpx.AsyncClient() as client:
        for i, hospital in enumerate(targets, 1):
            print(f"[{i:2d}/{len(targets)}] {hospital['name']} ... ", end="", flush=True)

            try:
                crawl_data = await crawl_one_hospital(
                    hospital["id"],
                    hospital["url"],
                    client,
                )

                main_page = next((p for p in crawl_data.pages if p.page_type == "main"), None)
                main_text_len = len(main_page.html_text) if main_page else 0
                total_text = sum(len(p.html_text) for p in crawl_data.pages)

                if main_text_len >= MIN_TEXT_THRESHOLD:
                    results["success"].append({
                        "name": hospital["name"],
                        "url": hospital["url"],
                        "pages": len(crawl_data.pages),
                        "total_text": total_text,
                        "specialty": hospital["specialty"],
                    })
                    print(f"✅ {len(crawl_data.pages)}페이지, {total_text}자")
                else:
                    results["js_needed"].append({
                        "name": hospital["name"],
                        "url": hospital["url"],
                        "main_text_len": main_text_len,
                        "specialty": hospital["specialty"],
                    })
                    print(f"⚠️ JS 렌더링 필요 ({main_text_len}자)")

            except Exception as e:
                results["failed"].append({
                    "name": hospital["name"],
                    "url": hospital["url"],
                    "error": str(e),
                })
                print(f"❌ 에러: {e}")

            # 예의상 딜레이
            await asyncio.sleep(0.5)

    print("\n" + "=" * 60)
    print("크롤링 결과 통계")
    print("=" * 60)
    print(f"  전체 대상: {len(targets)}개")
    print(f"  ✅ 성공 (텍스트 추출 OK): {len(results['success'])}개")
    print(f"  ⚠️ JS 렌더링 필요: {len(results['js_needed'])}개")
    print(f"  ❌ 실패 (접속 불가): {len(results['failed'])}개")

    success_rate = len(results["success"]) / len(targets) * 100 if targets else 0
    print(f"\n  성공률: {success_rate:.1f}%")

    if results["success"]:
        avg_text = sum(r["total_text"] for r in results["success"]) / len(results["success"])
        print(f"  성공 병원 평균 텍스트: {avg_text:.0f}자")

    output_path = os.path.join(PROJECT_ROOT, "be", "data", "crawl_stats.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  상세 결과 저장: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
