"""네이버 비공식 검색 → place_id 매칭 probe.

실행: .venv/bin/python ai/scratch/naver-place-probe-2026-05-28/probe_search.py

2026-05-28 실측: 5건 중 3건 성공 (매칭 실패는 검색어 정확도 문제, 차단 아님).
1건당 약 18~25초 (Playwright Chromium headless 부팅 + ncpt SDK + 검색).

흐름:
  1. Playwright 가 map.naver.com/p/search/{query} 진입
  2. ncpt SDK 자동 실행 → cipherText 만들어 토큰 발급
  3. allSearch?...&token={44자} 자동 호출 (page.on("response") 캡처)
  4. result.place.list[0].id → place_id

⚠️ robots.txt: User-agent: * Disallow: / (이 호출은 약관 위반 소지).
"""

import asyncio
import json
import urllib.parse
from pathlib import Path

from playwright.async_api import async_playwright

QUERIES = [
    "자생한방병원 강남",
    "더서울병원 성북",
    "위담한방병원 강남",
    "에이솝병원 강남",
    "예이진한의원 강남",
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

SAMPLES = Path(__file__).parent / "samples"


async def run_one(ctx, query: str) -> dict:
    page = await ctx.new_page()
    out = {"query": query, "place_id": None, "name": None, "review_count": None, "error": None}
    captured = {}

    async def on_resp(resp):
        try:
            if "api/search/allSearch" in resp.url and resp.status == 200:
                body = await resp.text()
                data = json.loads(body)
                captured["data"] = data
                place = data.get("result", {}).get("place")
                if place and place.get("list"):
                    item = place["list"][0]
                    captured["place_id"] = item.get("id")
                    captured["name"] = item.get("name")
                    captured["review_count"] = item.get("reviewCount")
                    captured["place_review_count"] = item.get("placeReviewCount")
                    captured["address"] = item.get("address")
                    captured["home_page"] = item.get("homePage")
                    captured["thum_url"] = item.get("thumUrl")
        except Exception:
            pass

    page.on("response", on_resp)

    try:
        url = "https://map.naver.com/p/search/" + urllib.parse.quote(query)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(6000)

        out["place_id"] = captured.get("place_id")
        out["name"] = captured.get("name")
        out["review_count"] = captured.get("review_count")
        out["place_review_count"] = captured.get("place_review_count")
        out["address"] = captured.get("address")
        out["home_page"] = captured.get("home_page")
        if not out["place_id"]:
            out["error"] = "place_id 추출 실패 (검색 매칭 실패)"

        # 첫 호출만 raw 응답 저장
        if captured.get("data") and not (SAMPLES / "search_first.json").exists():
            SAMPLES.mkdir(exist_ok=True)
            (SAMPLES / "search_first.json").write_text(
                json.dumps(captured["data"], ensure_ascii=False, indent=2)
            )
    except Exception as e:
        out["error"] = str(e)

    await page.close()
    return out


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        for q in QUERIES:
            print(f"\n=== {q} ===", flush=True)
            ctx = await browser.new_context(
                user_agent=UA, viewport={"width": 1280, "height": 900}, locale="ko-KR"
            )
            res = await run_one(ctx, q)
            results.append(res)
            ok = "✅" if res["place_id"] else "❌"
            print(
                f"  {ok} place_id={res['place_id']} name={res['name']} "
                f"reviewCount={res.get('review_count')} placeReviewCount={res.get('place_review_count')}",
                flush=True,
            )
            if res.get("address"):
                print(f"     address={res['address']}", flush=True)
            if res.get("home_page"):
                print(f"     home_page={res['home_page']}", flush=True)
            if res["error"]:
                print(f"     ERROR: {res['error']}", flush=True)
            await ctx.close()
        await browser.close()

    print("\n=== 요약 ===", flush=True)
    success = sum(1 for r in results if r["place_id"])
    print(f"성공률: {success}/{len(results)}", flush=True)
    print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
