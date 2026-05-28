"""카카오 블로그 (`tab/reviews/blog/{id}?page=N`) probe.

실행: .venv/bin/python ai/scratch/kakao-place-probe-2026-05-28/probe_blog.py

Endpoint: GET https://place-api.map.kakao.com/places/tab/reviews/blog/{place_id}?page={N}
- 카카오가 큐레이션한 외부 블로그 포스팅 (티스토리 + 카카오 본문 일부).
- 응답 `reviews[]` 의 각 항목: `title`·`contents` (요약 본문)·`url` (외부 블로그 원문)·`bloggername`·`bloggerprofileurl`·`datetime`.
- 네이버 `getPhotoViewerItems` 의 ugc `externalLink.url` 과 동일한 블로그 시드 URL 큐레이션 — **두 채널 합쳐 BlogSignal 시드 수집 가능**.

⚠️ robots.txt + 약관 자동화 금지.
"""

import json
from pathlib import Path

import httpx

PLACE_IDS = [
    "8094954",    # 춘원당한의원 (사용자 캡처)
    "27388604",   # 자생한방병원 강남
    "202729757",  # 더서울병원 성북
    "544191051",  # 위담한방병원 강남
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BLOG_URL = "https://place-api.map.kakao.com/places/tab/reviews/blog/{pid}"

SAMPLES = Path(__file__).parent / "samples"


def make_headers(place_id: str) -> dict:
    return {
        "User-Agent": UA,
        "Referer": f"https://place.map.kakao.com/{place_id}",
        "Origin": "https://place.map.kakao.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "pf": "web",
    }


def run_one(place_id: str, page: int = 1) -> dict:
    out = {
        "place_id": place_id,
        "page": page,
        "ok": False,
        "review_count": None,
        "items_len": 0,
        "first_keys": [],
        "first_url": None,
        "unique_hosts": [],
        "error": None,
    }
    try:
        r = httpx.get(
            BLOG_URL.format(pid=place_id),
            params={"page": page},
            headers=make_headers(place_id),
            timeout=15.0,
        )
        if r.status_code != 200:
            out["error"] = f"http {r.status_code}"
            return out
        data = r.json()
        out["ok"] = True
        out["review_count"] = data.get("review_count")
        items = data.get("reviews") or []
        out["items_len"] = len(items)
        if items:
            out["first_keys"] = sorted(list(items[0].keys()))
            out["first_url"] = items[0].get("url")
        hosts = set()
        for it in items:
            u = it.get("url") or ""
            if "//" in u:
                host = u.split("//", 1)[1].split("/", 1)[0]
                hosts.add(host)
        out["unique_hosts"] = sorted(hosts)
        SAMPLES.mkdir(parents=True, exist_ok=True)
        (SAMPLES / f"blog_{place_id}_p{page}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
    except Exception as exc:
        out["error"] = repr(exc)
    return out


def main() -> None:
    for pid in PLACE_IDS:
        print(json.dumps(run_one(pid, page=1), ensure_ascii=False))


if __name__ == "__main__":
    main()
