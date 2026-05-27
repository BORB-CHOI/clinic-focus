"""photoViewer + photoTabFilters probe.

실행: .venv/bin/python ai/scratch/naver-place-probe-2026-05-28/probe_photos.py

2026-05-28 실측:
  자생한방 강남: photos=46 (ibu=3 공식 / visitor=4 후기 / ugc=39 블로그), AI View 탭 노출
  더서울 성북: photos=61 (ibu=20 / visitor=1 / ugc=40)
  위담 강남: photos=60 (ibu=20 / ugc=40)
  619469917: photos=20 (ibu=1 / ugc=19)

핵심 시그널:
  ★ photos[].photoType = "ibu" | "visitor" | "ugc"
      ibu  = 병원이 네이버 플레이스에 직접 올린 사진 = 자칭 시그널 raw
      visitor = 방문자 후기 사진 (text 에 후기 본문 일부)
      ugc  = 외부 블로그 사진 (externalLink.url = blog.naver.com 시드 URL)
  ★ photos[].externalLink.url = 블로그 시그널 시드 URL (큐레이션된 매칭)
  ★ photoTabFilters.AI View.subTabFilters = 네이버가 사진 자동 분류 (INTERIOR/EXTERIOR)
"""

import asyncio
import json
from collections import Counter
from pathlib import Path

from playwright.async_api import async_playwright

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

SAMPLES = Path(__file__).parent / "samples"
QUERIES = Path(__file__).parent / "queries"

PLACES = [
    ("19516906", "자생한방병원_강남"),
    ("778531046", "더서울병원_성북"),
    ("1520927430", "위담한방병원_강남"),
    ("619469917", "정릉아동보건지소"),
]

CURSORS = [
    {"id": "biz"},
    {"id": "clip"},
    {"id": "cp0"},
    {"id": "aiView"},
    {"id": "placeReview"},
    {"id": "cp"},
]


def load_query(name: str) -> str:
    text = (QUERIES / name).read_text()
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


async def fetch_one(ctx, place_id: str, label: str):
    page = await ctx.new_page()
    print(f"\n=== {label} ({place_id}) ===", flush=True)

    # 사진 탭 진입 (쿠키 굳히기)
    detail_url = f"https://pcmap.place.naver.com/hospital/{place_id}/photo"
    await page.goto(detail_url, wait_until="domcontentloaded", timeout=40000)
    await page.wait_for_timeout(6000)

    common_input = {
        "businessId": place_id,
        "businessType": "hospital",
        "cursors": CURSORS,
        "dateRange": "",
        "excludeAuthorIds": [],
        "excludeClipIds": [],
        "excludeSection": [],
    }

    payload = [
        {
            "operationName": "getPhotoViewerItems",
            "variables": {"input": common_input},
            "query": load_query("photo_viewer_items.graphql"),
        },
        {
            "operationName": "getPhotoTabFilters",
            "variables": {"input": common_input},
            "query": load_query("photo_tab_filters.graphql"),
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

    SAMPLES.mkdir(exist_ok=True)
    (SAMPLES / f"photos_{label}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2)
    )

    for entry in data:
        d = entry.get("data") or {}
        if d.get("photoViewer"):
            pv = d["photoViewer"]
            photos = pv.get("photos") or []
            cursors = pv.get("cursors") or []
            types = Counter(p.get("photoType") for p in photos)
            print(f"  photos={len(photos)} types={dict(types)}", flush=True)
            for c in cursors:
                print(
                    f"    cursor.{c.get('id')}: startIndex={c.get('startIndex')} hasNext={c.get('hasNext')}",
                    flush=True,
                )

            # ugc(블로그) URL 시드 수집 — 블로그 시그널 시드 자동 큐레이션
            blog_seeds = [
                p.get("externalLink", {}).get("url")
                for p in photos
                if p.get("photoType") == "ugc" and (p.get("externalLink") or {}).get("url")
            ]
            unique_blogs = list(set(blog_seeds))
            print(f"  블로그 시드 URL (unique): {len(unique_blogs)} / 전체 ugc {len(blog_seeds)}", flush=True)
            for url in unique_blogs[:5]:
                print(f"    {url}", flush=True)

        if d.get("photoTabFilters"):
            tabs = (d["photoTabFilters"] or {}).get("tabFilters") or []
            print(f"  탭 필터: {[t.get('item') for t in tabs]}", flush=True)
            for t in tabs:
                subs = t.get("subTabFilters") or []
                if subs:
                    print(
                        f"    {t.get('item')!r} subs: {[(s.get('item'), s.get('code')) for s in subs]}",
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
