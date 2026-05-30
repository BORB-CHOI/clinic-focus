"""네이버 플레이스 후기 — **로컬 PC 실행용 standalone 크롤러** (AWS 의존 0).

왜 로컬인가: 네이버 place 후기는 ncpt 토큰 때문에 Playwright 필수인데, EC2 데이터센터
IP는 네이버 차단 표적이고 RAM 4GB 제약이 있다. 가정 IP·넉넉한 RAM의 로컬 PC가 더 안전·
빠르고 중간에 안 꺼진다. 단 지원계정 DDB/S3 쓰기 자격은 로컬에 없으므로(IAM Role 전용),
이 스크립트는 **raw JSON 파일로만 저장**하고, EC2 에서 parse+DDB 적재한다(파일 다리).

매칭 전략 = 좌표 앵커 + 이름 확정 하이브리드:
  HIRA 정확 좌표로 네이버 place 후보를 검색(searchCoord 바이어스)하고, 후보 중
  거리(haversine) + 이름 부분일치 점수가 가장 높은 곳의 place_id 를 택한다.
  → 키워드 단독(generic 한의원 실패)·좌표 단독(같은 건물 옆 클리닉 오매칭) 둘 다 회피.

[내 PC에서 할 일]
  1) Python 3.10+ 설치 후:
        pip install playwright
        python -m playwright install chromium
  2) EC2 에서 받은 파일 두 개를 이 스크립트와 같은 폴더에 둔다:
        crawl_naver_local.py  (이 파일)
        naver_targets.json    (병원 목록: id/name/address/lat/lng/kakao_matched)
  3) 먼저 3개만 연기테스트(매칭·후기가 제대로 잡히는지 눈으로 확인):
        python crawl_naver_local.py --limit 3
     → naver_raw/ 에 JSON 이 생기고, 콘솔에 [OK] place_id·후기수가 찍히면 성공.
  4) 잘 되면 전체(혹은 원하는 만큼):
        python crawl_naver_local.py --limit 800
     중단됐다 다시 켜도 이미 받은 건 건너뛴다(resume). 천천히 — 기본 2.0초 간격.
  5) 다 돌면 naver_raw/ 폴더를 통째로 EC2 로 전송:
        scp -r naver_raw/  <ec2>:~/clinic-focus/be/data/naver_raw/
     EC2 쪽에서 parse+DDB 적재 스크립트가 받아서 처리한다.

⚠️ 회색지대: pcmap.place.naver.com 은 robots/약관상 자동수집 금지. 시연 표본 한정,
   천천히. 차단되면 즉시 중단하고 간격을 늘려라.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import sys
import time

# ── 네이버 내부 endpoint·쿼리 (기존 검증된 어댑터에서 그대로) ──────────────
_GRAPHQL_URL = "https://pcmap-api.place.naver.com/graphql"
_DETAIL_URL = "https://pcmap.place.naver.com/hospital/{pid}/review/visitor"
_SEARCH_API = "https://map.naver.com/p/api/search/allSearch"
_MAP_HOME = "https://map.naver.com/"
_CID_LIST = ["223175", "223176", "223192", "228995"]  # 병원/의원 카테고리
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# getVisitorReviews — 사용자 브라우저 캡처(2026-05-28) 검증본.
_VISITOR_QUERY = """
query getVisitorReviews($input: VisitorReviewsInput) {
  visitorReviews(input: $input) {
    items {
      id reviewId rating body visitCount viewCount visited visitedDate created
      votedKeywords { code name }
      userIdno loginIdno nickname
    }
    starDistribution { score count }
    total score
  }
}
""".strip()


def _haversine(lat1, lng1, lat2, lng2) -> float:
    """두 좌표 거리(m)."""
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _norm(s: str) -> str:
    """이름 비교용 정규화: 공백·괄호·진료과 접미사 제거."""
    s = re.sub(r"\(.*?\)", "", s or "")
    s = re.sub(r"\s+", "", s)
    return s


def _name_score(target: str, cand: str) -> float:
    """이름 부분일치 점수 0~1 (양방향 substring)."""
    a, b = _norm(target), _norm(cand)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    # 핵심 토큰(접미사 제거) 부분일치
    core = re.sub(r"(의원|병원|클리닉|피부과|성형외과|치과|한의원|정형외과|내과|이비인후과|안과|산부인과|소아과|의원$)", "", a)
    return 1.0 if core and core in b else 0.0


async def _resolve_place_id(page, name: str, lat: float, lng: float) -> tuple[str | None, dict]:
    """좌표 앵커 검색 → 후보 중 거리+이름 최적 place_id. (place_id, 진단dict) 반환."""
    q = name
    url = (
        f"{_SEARCH_API}?query={q}&type=all"
        f"&searchCoord={lng};{lat}&boundary="
    )
    try:
        res = await page.evaluate(
            """async (u) => {
                const r = await fetch(u, {headers: {"referer": "https://map.naver.com/"}});
                return {status: r.status, text: await r.text()};
            }""",
            url,
        )
    except Exception as e:  # noqa: BLE001
        return None, {"err": f"search fetch 실패: {e}"}
    if res.get("status") != 200:
        return None, {"err": f"search HTTP {res.get('status')}"}
    try:
        data = json.loads(res["text"])
    except ValueError:
        return None, {"err": "search 비JSON"}

    # allSearch 응답에서 place 후보 리스트를 방어적으로 추출
    cands = []
    try:
        plist = (((data.get("result") or {}).get("place") or {}).get("list")) or []
        for it in plist:
            cands.append({
                "id": str(it.get("id") or ""),
                "name": it.get("name") or it.get("title") or "",
                "lat": float(it["y"]) if it.get("y") else None,
                "lng": float(it["x"]) if it.get("x") else None,
            })
    except Exception as e:  # noqa: BLE001
        return None, {"err": f"파싱 실패: {e}", "keys": list(data.keys())}

    if not cands:
        return None, {"err": "후보 0", "keys": list(data.keys())}

    # 점수 = 이름일치(가중 0.6) + 거리근접(가중 0.4, 300m 이내 만점)
    best, best_score = None, -1.0
    for c in cands:
        if not c["id"]:
            continue
        ns = _name_score(name, c["name"])
        if c["lat"] and c["lng"]:
            d = _haversine(lat, lng, c["lat"], c["lng"])
            ds = max(0.0, 1.0 - d / 300.0)
        else:
            d, ds = None, 0.0
        score = ns * 0.6 + ds * 0.4
        if score > best_score:
            best, best_score = c, score
            best["_dist_m"] = round(d) if d is not None else None
            best["_namescore"] = ns
    # 최소 신뢰: 이름이 전혀 안 맞고(0) 거리도 멀면(>300m) 버림
    if best and (best["_namescore"] > 0 or (best.get("_dist_m") or 9999) <= 150):
        return best["id"], {"picked": best, "n_cands": len(cands)}
    return None, {"err": "신뢰 미달", "best": best, "n_cands": len(cands)}


async def _fetch_visitor_reviews(page, place_id: str, size: int = 20) -> dict | None:
    """place_id 방문자 후기 raw(graphql). 상세 진입→토큰 발급→fetch."""
    payload = [{
        "operationName": "getVisitorReviews",
        "variables": {"input": {
            "businessId": place_id, "businessType": "hospital",
            "cidList": _CID_LIST, "includeContent": True, "size": size, "page": 1,
        }},
        "query": _VISITOR_QUERY,
    }]
    try:
        await page.goto(_DETAIL_URL.format(pid=place_id),
                        wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(3500)  # ncpt 토큰 발급 대기 (6초→3.5초 단축)
        res = await page.evaluate(
            """async ([url, body]) => {
                const r = await fetch(url, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    credentials: "include",
                    body: JSON.stringify(body),
                });
                return {status: r.status, text: await r.text()};
            }""",
            [_GRAPHQL_URL, payload],
        )
    except Exception as e:  # noqa: BLE001
        return {"_error": f"review fetch 실패: {e}"}
    if res.get("status") != 200:
        return {"_error": f"review HTTP {res.get('status')}"}
    try:
        return json.loads(res["text"])
    except ValueError:
        return {"_error": "review 비JSON"}


async def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="네이버 플레이스 후기 로컬 크롤 (raw JSON 저장)")
    ap.add_argument("--targets", default="naver_targets.json", help="병원 목록 JSON")
    ap.add_argument("--out", default="naver_raw", help="raw JSON 저장 폴더")
    ap.add_argument("--limit", type=int, default=0, help="처리 개수 (0=전체)")
    ap.add_argument("--delay", type=float, default=2.0, help="병원 간 간격(초). 차단되면 늘려라")
    ap.add_argument("--size", type=int, default=20, help="병원당 후기 수")
    args = ap.parse_args(argv)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("playwright 미설치 — `pip install playwright && python -m playwright install chromium`")
        sys.exit(1)

    targets = json.load(open(args.targets, encoding="utf-8"))
    os.makedirs(args.out, exist_ok=True)

    todo = [t for t in targets if not os.path.exists(os.path.join(args.out, f"{t['hospital_id']}.json"))]
    if args.limit:
        todo = todo[:args.limit]
    print(f"대상 {len(targets)} / 미처리 {len(todo)} (이번 실행 {len(todo) if not args.limit else min(args.limit, len(todo))})")
    print(f"저장 폴더: {args.out}/  | 간격 {args.delay}s | 후기 {args.size}건/병원\n")

    ok = matched = reviews_found = failed = 0
    start = time.time()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(user_agent=_UA, viewport={"width": 1280, "height": 900}, locale="ko-KR")
        page = await ctx.new_page()
        await page.goto(_MAP_HOME, wait_until="domcontentloaded", timeout=40000)  # 세션/쿠키
        await page.wait_for_timeout(1500)

        for i, t in enumerate(todo, 1):
            hid, name = t["hospital_id"], t["name"]
            lat, lng = t.get("lat"), t.get("lng")
            rec = {"hospital_id": hid, "name": name, "place_id": None,
                   "visitor_reviews_raw": None, "diag": {}}

            pid, diag = await _resolve_place_id(page, name, lat, lng)
            rec["place_id"] = pid
            rec["diag"]["resolve"] = diag
            if pid:
                matched += 1
                reviews = await _fetch_visitor_reviews(page, pid, args.size)
                rec["visitor_reviews_raw"] = reviews
                n = 0
                try:
                    vr = reviews[0]["data"]["visitorReviews"]
                    n = len(vr.get("items") or [])
                except Exception:  # noqa: BLE001
                    n = -1
                if n > 0:
                    reviews_found += 1
                tag = f"place_id={pid} 후기 {n}건"
            else:
                failed += 1
                tag = f"매칭실패 ({diag.get('err','?')})"

            json.dump(rec, open(os.path.join(args.out, f"{hid}.json"), "w"),
                      ensure_ascii=False, indent=1)
            ok += 1
            print(f"[{i}/{len(todo)}] {'✅' if pid else '❌'} {name[:20]} — {tag}")

            if i % 50 == 0:
                el = time.time() - start
                eta = (len(todo) - i) * (el / i)
                print(f"  📊 {i}/{len(todo)} | 매칭 {matched} 후기보유 {reviews_found} 실패 {failed} "
                      f"| ETA {int(eta//60)}분")
            await asyncio.sleep(args.delay)

        await browser.close()

    print(f"\n완료 — 처리 {ok} / 매칭 {matched} / 후기보유 {reviews_found} / 실패 {failed}")
    print(f"raw JSON: {args.out}/  → scp 로 EC2 ~/clinic-focus/be/data/naver_raw/ 로 전송")


if __name__ == "__main__":
    asyncio.run(main())
