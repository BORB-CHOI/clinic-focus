"""visitorReviews + visitorReviewStats probe.

실행: .venv/bin/python ai/scratch/naver-place-probe-2026-05-28/probe_reviews.py

2026-05-28 실측 결과:
  - 자생한방 강남 (19516906): total=526, avg=4.05, authorCount=113
  - 더서울 성북 (778531046): total=356, avg=4.02, authorCount=64
  - 위담 강남 (1520927430): total=1002, avg=4.24, authorCount=228
  - 619469917: total=2, avg=0 (소규모 보건지소)

핵심:
  - items[].body 후기 본문 raw 안정 수집
  - items[].rating 은 병원 카테고리 전부 null (네이버가 별점 미수집)
  - items[].themes / votedKeywords 빈 배열 (네이버가 병원 카테고리 통계 미제공)
  - author.nickname 은 서버측 일부 마스킹 (su****·까뀽2·ymn****)
  - userIdno = 작성자 익명 5자 ID, loginIdno = 비로그인 호출 시 ""
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

SAMPLES = Path(__file__).parent / "samples"
QUERIES = Path(__file__).parent / "queries"

# 표본 4건
PLACES = [
    ("19516906", "자생한방병원_강남"),
    ("778531046", "더서울병원_성북"),
    ("1520927430", "위담한방병원_강남"),
    ("619469917", "정릉아동보건지소"),
]

# 병원,의원 카테고리 ID (사용자 캡처 619469917 의 cidList 그대로)
CID_LIST = ["223175", "223176", "223192", "228995"]


def load_query(name: str) -> str:
    text = (QUERIES / name).read_text()
    # GraphQL 파일에 # 주석은 GraphQL 표준에서 허용되지만 보수적으로 # 줄 제거
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


async def fetch_one(ctx, place_id: str, label: str):
    page = await ctx.new_page()
    print(f"\n=== {label} ({place_id}) ===", flush=True)

    # 상세 페이지 진입(쿠키·세션 굳히기)
    detail_url = f"https://pcmap.place.naver.com/hospital/{place_id}/review/visitor"
    await page.goto(detail_url, wait_until="domcontentloaded", timeout=40000)
    await page.wait_for_timeout(6000)

    payload = [
        {
            "operationName": "getVisitorReviews",
            "variables": {
                "input": {
                    "businessId": place_id,
                    "bookingBusinessId": None,
                    "businessType": "hospital",
                    "cidList": CID_LIST,
                    "includeContent": True,
                    "size": 3,
                }
            },
            "query": load_query("visitor_reviews.graphql"),
        },
        {
            "operationName": "getVisitorReviewStats",
            "variables": {"id": place_id, "itemId": "0", "businessType": "hospital"},
            "query": load_query("visitor_review_stats.graphql"),
        },
    ]

    result = await page.evaluate(
        """async (body) => {
            const r = await fetch("https://pcmap-api.place.naver.com/graphql", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                credentials: "include",
                body: JSON.stringify(body),
            });
            return {status: r.status, text: await r.text()};
        }""",
        payload,
    )

    print(f"  HTTP {result['status']}", flush=True)
    if result["status"] != 200:
        print(f"  본문 앞 300: {result['text'][:300]}", flush=True)
        await page.close()
        return

    data = json.loads(result["text"])

    # raw 저장
    SAMPLES.mkdir(exist_ok=True)
    (SAMPLES / f"reviews_{label}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2)
    )

    for entry in data:
        d = entry.get("data") or {}
        if d.get("visitorReviews"):
            vr = d["visitorReviews"]
            print(f"  visitorReviews total={vr.get('total')} score={vr.get('score')}", flush=True)
            for k, item in enumerate((vr.get("items") or [])[:3]):
                print(
                    f"    [{k}] visited={item.get('visitedDate')} "
                    f"rating={item.get('rating')} visitCount={item.get('visitCount')}",
                    flush=True,
                )
                print(
                    f"        author={item.get('author', {}).get('nickname')} "
                    f"userIdno={item.get('userIdno')}",
                    flush=True,
                )
                print(f"        body: {(item.get('body') or '')[:80]}", flush=True)
        if d.get("visitorReviewStats"):
            vrs = d["visitorReviewStats"]
            rev = vrs.get("review") or {}
            ana = vrs.get("analysis") or {}
            vk = ana.get("votedKeyword") or {}
            print(
                f"  Stats avgRating={rev.get('avgRating')} total={rev.get('totalCount')} "
                f"authorCount={rev.get('authorCount')} imageReviewCount={rev.get('imageReviewCount')}",
                flush=True,
            )
            print(
                f"        votedKeyword.total={vk.get('totalCount')} "
                f"themes={len(ana.get('themes') or [])} menus={len(ana.get('menus') or [])}",
                flush=True,
            )
        if "errors" in entry:
            print(f"  errors: {entry['errors']}", flush=True)

    await page.close()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            user_agent=UA, viewport={"width": 1280, "height": 900}, locale="ko-KR"
        )
        for place_id, label in PLACES:
            await fetch_one(ctx, place_id, label)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
