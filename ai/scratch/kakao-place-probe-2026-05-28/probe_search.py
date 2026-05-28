"""카카오 비공식 검색 → place_id 매칭 probe.

실행: .venv/bin/python ai/scratch/kakao-place-probe-2026-05-28/probe_search.py

2026-05-28 실측 (사용자 캡처 기반):
  - Endpoint: GET https://m.map.kakao.com/actions/searchJson
  - Param: type=PLACE&q={쿼리}&pageNo={1..}
  - wxEnc/wyEnc 좌표 enc 는 선택. 없어도 동작.
  - PC UA + Referer=`https://m.map.kakao.com/actions/searchView` + `X-Requested-With: XMLHttpRequest` 박으면 200.
  - 모바일 UA 또는 Referer 누락 시 302 → `https://www.kakao.com/500.ko.html` (봇 차단).
  - ncpt 같은 토큰 발급 절차 없음. httpx 단발 호출 가능.

⚠️ robots.txt: User-agent: * Disallow: / (이 호출은 약관 위반 소지).
"""

import json
from pathlib import Path
from urllib.parse import urlencode

import httpx

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

HEADERS = {
    "User-Agent": UA,
    "Referer": "https://m.map.kakao.com/actions/searchView",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

SEARCH_URL = "https://m.map.kakao.com/actions/searchJson"
SAMPLES = Path(__file__).parent / "samples"


def run_one(client: httpx.Client, query: str) -> dict:
    out = {
        "query": query,
        "place_id": None,
        "name": None,
        "review_count": None,
        "category": None,
        "first_3_names": [],
        "total_count": None,
        "error": None,
    }
    params = {"type": "PLACE", "q": query, "pageNo": 1}
    try:
        r = client.get(SEARCH_URL, params=params, follow_redirects=False)
        if r.status_code != 200:
            out["error"] = f"http {r.status_code} {r.headers.get('location', '')}"
            return out
        data = r.json()
        place_list = data.get("placeList") or []
        out["total_count"] = len(place_list)
        out["first_3_names"] = [p.get("name") for p in place_list[:3]]
        if not place_list:
            out["error"] = "empty placeList"
            return out
        top = place_list[0]
        out["place_id"] = str(top.get("confirmid") or top.get("id") or "")
        out["name"] = top.get("name")
        out["review_count"] = top.get("reviewCount")
        out["category"] = top.get("cate_name_depth2") or top.get("cate_name_depth3")
        SAMPLES.mkdir(parents=True, exist_ok=True)
        safe = query.replace(" ", "_").replace("/", "_")
        (SAMPLES / f"search_{safe}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
    except Exception as exc:
        out["error"] = repr(exc)
    return out


def main() -> None:
    with httpx.Client(headers=HEADERS, timeout=15.0) as client:
        for q in QUERIES:
            r = run_one(client, q)
            print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
