"""병원 자체운영 블로그 발견 — 외부 시드에서 '병원이 직접 쓴' blog.naver.com/{ID} 추출.

목적: 이미 DDB 에 적재된 외부 블로그 시드(NAVER#BLOG.posts[].link · KAKAO#BLOG.seeds[].origin_url)
에서 **병원 자체운영 블로그**(blog.naver.com/{병원ID})를 찾아, 홈페이지가 없는 병원의
contact.website_url 로 저장한다. 저장된 URL 은 다음 크롤 사이클에서 자체사이트로 크롤되어
자칭(self_claim) 시그널로 흡수된다 (enrich_urls._is_real_website 가 blog.naver.com 을 허용).

⚠️ 저자 기준 (혼동 금지):
  - 이 스크립트가 찾는 건 '병원이 직접 운영하는 블로그' = self_claim 동류.
    한 병원의 시드들이 같은 블로그 ID 로 수렴하면(같은 채널을 반복 인용) 그게 병원 공식 채널일
    개연성이 높다 → website_url 로 저장해 크롤 시 self_claim 으로 흡수하는 이유가 그것.
  - 반대로 여러 ID 로 분산되면 제3자(후기 블로거)들의 글이므로 외부 후기(BlogSignal/naver_blog
    시그널)로 남겨두고 website_url 로 승격하지 않는다.

네트워크는 URLValidator 검증 1회뿐(가벼움). 천천히 — 검증 사이에 간격을 둔다.

실행: .venv/bin/python be/scripts/discover_official_blogs.py [--sigungu 강남구] [--confirm] [--min-posts 3]
  --confirm 없으면 dry-run (DDB 쓰기 안 함, 후보만 출력).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time

# 터미널에 즉시 출력 (버퍼링 끄기)
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.adapters.dynamo_adapter import DynamoAdapter
from be.core.url_validator import URLValidator


# blog.naver.com 의 블로그 ID 를 경로/쿼리 변형에서 안전하게 뽑는다.
#   https://blog.naver.com/{ID}                       → ID
#   https://blog.naver.com/{ID}/223...                → ID (포스트 경로)
#   https://blog.naver.com/{ID}?Redirect=...          → ID (쿼리)
#   https://m.blog.naver.com/{ID}/223...              → ID (모바일)
#   https://blog.naver.com/PostView.naver?blogId={ID} → ID (구형 PostView 쿼리형)
# 블로그 ID 규칙: 영문/숫자/_/- (네이버 아이디 문자셋). PostView·PostList 등 시스템
# 경로 토큰은 ID 가 아니므로 제외한다.
_BLOG_HOST_RE = re.compile(
    r"https?://(?:m\.)?blog\.naver\.com/([A-Za-z0-9_-]+)", re.IGNORECASE
)
_BLOGID_QUERY_RE = re.compile(r"[?&]blogId=([A-Za-z0-9_-]+)", re.IGNORECASE)

# 경로 첫 토큰이지만 블로그 ID 가 아닌 시스템 엔드포인트들 (이 경우 ?blogId= 로 폴백).
_NON_ID_PATH_TOKENS = {
    "postview.naver", "postlist.naver", "prologue.naver",
    "postview", "postlist", "prologue", "guestbook.naver",
}


def extract_blog_id(url: str) -> str | None:
    """blog.naver.com URL 에서 블로그 ID 1개를 추출. 못 찾으면 None.

    경로 첫 토큰이 PostView.naver 같은 시스템 엔드포인트면 ?blogId= 쿼리로 폴백한다.
    """
    if not url or "blog.naver.com" not in url.lower():
        return None

    m = _BLOG_HOST_RE.search(url)
    if m:
        token = m.group(1)
        if token.lower() not in _NON_ID_PATH_TOKENS:
            return token

    # 시스템 경로(PostView.naver 등) → blogId 쿼리 파라미터로 폴백
    q = _BLOGID_QUERY_RE.search(url)
    if q:
        return q.group(1)
    return None


def collect_seed_urls(external: dict) -> list[str]:
    """load_external_signals dict 에서 블로그 시드 URL 들을 모은다.

    load_external_signals 는 키별로 None 또는 PK/SK 제거된 dict 를 준다:
      - external["naver_blog"] = {"total", "keyword_frequency", "posts": [{"link", ...}]}  (NaverBlog)
      - external["kakao_blog"] = {"total_posts", "seeds": [{"origin_url", ...}]}            (KakaoBlog)
    dict 접근은 전부 .get 으로 방어 (entity 미적재 시 None, 스키마 변형 대비).
    """
    urls: list[str] = []

    naver_blog = external.get("naver_blog")
    if isinstance(naver_blog, dict):
        for post in naver_blog.get("posts") or []:
            if isinstance(post, dict):
                link = post.get("link")
                if isinstance(link, str) and link:
                    urls.append(link)

    kakao_blog = external.get("kakao_blog")
    if isinstance(kakao_blog, dict):
        for seed in kakao_blog.get("seeds") or []:
            if isinstance(seed, dict):
                origin = seed.get("origin_url")
                if isinstance(origin, str) and origin:
                    urls.append(origin)

    return urls


def pick_official_blog_id(urls: list[str], min_posts: int) -> tuple[str | None, dict[str, int]]:
    """시드 URL 들에서 ID별 등장 횟수를 세고, 최빈 ID 가 min_posts 이상이면 그 ID 를 반환.

    Returns:
        (official_id_or_None, id별_카운트_dict)
        - 최빈 ID 의 카운트가 min_posts 미만이면 official_id=None (제3자 후기로 판단, 제외).
    """
    counts: dict[str, int] = {}
    for url in urls:
        bid = extract_blog_id(url)
        if bid:
            counts[bid] = counts.get(bid, 0) + 1

    if not counts:
        return None, counts

    top_id, top_count = max(counts.items(), key=lambda kv: kv[1])
    if top_count >= min_posts:
        return top_id, counts
    return None, counts


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="병원 자체운영 블로그(blog.naver.com/{ID}) 발견 → website_url 보강"
    )
    parser.add_argument(
        "--sigungu", default="강남구",
        help="대상 시군구 (기본 강남구).",
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="지정 시 DDB update_website_url 실행. 미지정 시 dry-run (출력만).",
    )
    parser.add_argument(
        "--min-posts", type=int, default=3,
        help="한 병원에서 같은 블로그 ID 가 이 횟수 이상 등장해야 공식 블로그로 인정 (기본 3).",
    )
    args = parser.parse_args(argv)

    db = DynamoAdapter()
    validator = URLValidator()

    mode = "CONFIRM (DDB 쓰기)" if args.confirm else "DRY-RUN (출력만)"
    print("=" * 60)
    print(f"자체운영 블로그 발견 — {args.sigungu} | {mode} | min-posts={args.min_posts}")
    print("=" * 60)

    # 1. 대상 시군구 META 조회. website_url 이미 있으면 skip (자체사이트 보유).
    print(f"\nDynamoDB 에서 {args.sigungu} 병원 조회 중...")
    hospitals = db.list_hospitals_by_sigungu(args.sigungu)
    targets = [h for h in hospitals if not (h.contact and h.contact.website_url)]

    print(f"  전체: {len(hospitals)}개")
    print(f"  URL 보유(스킵): {len(hospitals) - len(targets)}개")
    print(f"  대상(URL 없음): {len(targets)}개\n")

    candidates = 0   # min-posts 충족 후보
    validated = 0    # URLValidator 통과
    saved = 0        # DDB 저장 (confirm 시)
    rejected = 0     # 후보였으나 검증 실패
    total = len(targets)
    start_time = time.time()

    for i, hospital in enumerate(targets, 1):
        hid = hospital.hospital_id

        external = db.load_external_signals(hid)
        seed_urls = collect_seed_urls(external)
        if not seed_urls:
            continue

        official_id, counts = pick_official_blog_id(seed_urls, args.min_posts)
        if not official_id:
            continue

        candidates += 1
        url = f"https://blog.naver.com/{official_id}"
        top_count = counts[official_id]
        distinct = len(counts)

        # 7. 검증 — 네트워크는 여기뿐. 천천히 (검증 후 간격).
        validated_url = await validator.validate(url)
        if not validated_url:
            rejected += 1
            print(f"  [{i}/{total}] ⚠️  {hospital.name} — {official_id} "
                  f"({top_count}회/ID {distinct}종) → 검증 실패, 스킵")
            await asyncio.sleep(0.3)
            continue

        validated += 1
        if args.confirm:
            db.update_website_url(hid, validated_url)
            saved += 1
            tag = "💾 저장"
        else:
            tag = "🔎 후보(dry-run)"

        print(f"  [{i}/{total}] ✅ {tag} {hospital.name} → {validated_url} "
              f"(시드 {top_count}회 / 서로 다른 ID {distinct}종)")

        # 가벼운 부하라도 천천히
        await asyncio.sleep(0.3)

        # 50개마다 진행률 + ETA
        if i % 50 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            remaining = total - i
            eta = remaining / rate if rate > 0 else 0
            print(f"  📊 [{i}/{total}] {i / total * 100:.0f}% | "
                  f"후보:{candidates} 검증통과:{validated} 저장:{saved} | "
                  f"ETA {int(eta // 60)}분 {int(eta % 60)}초")

    print("\n" + "=" * 60)
    print("리포트")
    print("=" * 60)
    print(f"  대상(URL 없음):       {total}개")
    print(f"  min-posts 충족 후보:  {candidates}개")
    print(f"  URLValidator 통과:    {validated}개")
    print(f"  검증 실패(후보 중):   {rejected}개")
    if args.confirm:
        print(f"  DDB 저장:             {saved}개")
    else:
        print(f"  DRY-RUN — 저장 안 함. --confirm 시 {validated}개 저장 예정.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
