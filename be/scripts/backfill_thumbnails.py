"""대표 이미지(thumbnail_url) 백필 v2.

소스 우선순위 (사용자 결정 2026-06-04 보강):
  1) 카카오/네이버 대표사진 (KAKAO#PLACE.representative_image_url) — 외부 CDN URL 직접.
  2) 홈페이지 메인화면 스크린샷 (Playwright screenshot_hero → Pillow 축소 JPG → S3
     thumbnails/{id}.jpg → thumbnail_url=/api/hospitals/{id}/thumbnail, BE 가 스트리밍).
  3) 둘 다 없으면 None → FE 회색 '이미지 없음' 플레이스홀더.

★ 크롤 <img> 픽은 폐기 — 로고·아이콘 등 잡것이 섞여 '이상한 아이콘' 노출 원인이었음.

모드:
  --mode kakao       카카오 대표사진만(빠름) + 옛 크롤 <img> 잡픽 정리(clear).
  --mode screenshot  thumbnail 없는 website_url 보유 병원 홈페이지 스크린샷(느림, 재개가능).
  --mode both        kakao 먼저 → 그다음 screenshot.

실행:
  .venv/bin/python be/scripts/backfill_thumbnails.py --mode kakao --sigungu 강남구 --force
  .venv/bin/python be/scripts/backfill_thumbnails.py --mode screenshot --sigungu 강남구
"""

from __future__ import annotations

import argparse
import asyncio
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from PIL import Image, ImageStat  # noqa: E402

from be.adapters.dynamo_adapter import DynamoAdapter  # noqa: E402
from be.adapters.s3_adapter import S3Adapter  # noqa: E402

# 홈페이지가 아닌 URL(블로그·플레이스·SNS·예약)은 스크린샷 대상에서 제외 —
# 메인화면이 아니거나 헤드리스를 차단(blog.naver 등)해 잡 화면이 찍힌다.
_NON_HOMEPAGE_HOSTS = (
    "blog.naver.com", "cafe.naver.com", "m.cafe.naver", "place.naver.com", "m.place.naver",
    "booking.naver.com", "pcmap.place.naver", "blog.me", "post.naver.com",
    "instagram.com", "facebook.com", "youtube.com", "youtu.be", "band.us",
    "pf.kakao.com", "story.kakao", "smartstore.naver", "map.naver.com", "map.kakao",
)

# https 지원 확인된 대표이미지 CDN — http 로 와도 https 로 업그레이드.
_HTTPS_SAFE_HOSTS = ("pstatic.net", "kakaocdn.net", "daumcdn.net")
# '깨끗한' 외부 대표이미지로 인정하는 호스트(잡픽 정리 시 보존 판정).
_CLEAN_HOSTS = _HTTPS_SAFE_HOSTS

# 스크린샷 썸네일 폭(px). 1280×800 캡처를 이 폭으로 축소(JPG).
_THUMB_WIDTH = 640
# 스크린샷 동시 처리 수(브라우저 semaphore=3 위에서 약간 더 큐잉).
_SCREENSHOT_CONCURRENCY = 6


def _upgrade_scheme(url: str) -> str:
    if url.startswith("http://") and any(h in url for h in _HTTPS_SAFE_HOSTS):
        return "https://" + url[len("http://"):]
    return url


def pick_kakao_image(db: DynamoAdapter, hospital_id: str) -> str | None:
    """KAKAO#PLACE.representative_image_url (있으면 https 정규화)."""
    place = db.get_entity(hospital_id, "KAKAO#PLACE")
    if not place:
        return None
    url = (place.get("representative_image_url") or "").strip()
    return _upgrade_scheme(url) if url else None


def _is_clean_thumbnail(url: str | None) -> bool:
    """현재 thumbnail_url 이 보존 대상(카카오 CDN 또는 우리 스크린샷)인가.

    그 외(옛 크롤 <img> 픽)는 잡픽이므로 정리한다.
    """
    if not url:
        return False
    if url.startswith("/api/"):  # 우리가 올린 스크린샷(BE 스트리밍)
        return True
    return any(h in url for h in _CLEAN_HOSTS)


# ── 모드 1: 카카오 대표사진 + 잡픽 정리 ──────────────────────────────────────

def run_kakao(db: DynamoAdapter, metas, force: bool, dry: bool) -> None:
    n_set = n_keep = n_clear = n_none = 0
    for i, meta in enumerate(metas, 1):
        hid = meta.hospital_id
        cur = meta.thumbnail_url
        kakao = pick_kakao_image(db, hid)
        if kakao:
            if cur == kakao and not force:
                n_keep += 1
                continue
            if not dry:
                db.update_thumbnail_url(hid, kakao)
            n_set += 1
        else:
            # 카카오 없음 — 현재 thumbnail 이 잡픽(크롤 <img>)이면 정리, 깨끗하면 보존.
            if _is_clean_thumbnail(cur):
                n_keep += 1
            elif cur:
                if not dry:
                    db.update_thumbnail_url(hid, None)
                n_clear += 1
            else:
                n_none += 1
        if i % 400 == 0:
            print(f"  [{i}/{len(metas)}] … 카카오 {n_set} / 잡픽정리 {n_clear}")
    print("-" * 56)
    print(f"✅ 카카오 설정 {n_set} · 보존 {n_keep} · 잡픽 정리 {n_clear} · 무이미지 {n_none}")


# ── 모드 2: 홈페이지 스크린샷 ────────────────────────────────────────────────

def _is_homepage_url(url: str) -> bool:
    """블로그·플레이스·SNS·예약 링크면 False(스크린샷 대상 제외)."""
    u = url.lower()
    return not any(h in u for h in _NON_HOMEPAGE_HOSTS)


def _to_jpg_thumb(png: bytes) -> bytes | None:
    """PNG 캡처를 폭 _THUMB_WIDTH JPG 로 축소. 거의 단색(빈 화면)이면 None."""
    img = Image.open(io.BytesIO(png)).convert("RGB")
    # 빈/로딩 실패 화면 게이트 — 그레이스케일 표준편차가 매우 낮으면 단색(흰 화면).
    if ImageStat.Stat(img.convert("L")).stddev[0] < 6.0:
        return None
    w, h = img.size
    if w > _THUMB_WIDTH:
        img = img.resize((_THUMB_WIDTH, max(1, round(h * _THUMB_WIDTH / w))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


async def run_screenshots(db: DynamoAdapter, s3: S3Adapter, metas, force: bool, dry: bool) -> None:
    from be.core.browser_manager import BrowserManager

    # 대상: 홈페이지 URL 보유 + (thumbnail 없음 OR 우리 스크린샷(/api/)).
    # ★ 카카오 외부 CDN thumbnail 은 절대 덮지 않는다(더 깨끗). 우리 옛 스크린샷은 재평가(게이트 적용).
    def _is_target(m) -> bool:
        if not (m.contact and m.contact.website_url):
            return False
        if not _is_homepage_url(m.contact.website_url):
            return False
        cur = m.thumbnail_url
        return (not cur) or cur.startswith("/api/")

    targets = [m for m in metas if _is_target(m)]
    print(f"스크린샷 대상(홈페이지 URL + 카카오 아님): {len(targets)}곳")
    print("-" * 56)
    done = junk = fail = 0
    sem = asyncio.Semaphore(_SCREENSHOT_CONCURRENCY)

    async with BrowserManager() as bm:
        async def one(meta) -> None:
            nonlocal done, junk, fail
            url = meta.contact.website_url
            if not url.startswith(("http://", "https://")):
                url = "http://" + url
            async with sem:
                png = await bm.screenshot_hero(url)  # 정크 페이지면 None
            jpg = None
            if png:
                try:
                    jpg = _to_jpg_thumb(png)  # 빈 화면이면 None
                except Exception:  # noqa: BLE001
                    jpg = None
            if jpg:
                if not dry:
                    s3.save_thumbnail(meta.hospital_id, jpg)
                    db.update_thumbnail_url(meta.hospital_id, f"/api/hospitals/{meta.hospital_id}/thumbnail")
                done += 1
            else:
                # 정크/빈/실패 — 옛 스크린샷 thumbnail 이 남아있으면 정리(회색 플레이스홀더로).
                if (meta.thumbnail_url or "").startswith("/api/") and not dry:
                    db.update_thumbnail_url(meta.hospital_id, None)
                if png is None:
                    junk += 1   # 정크 게이트(파킹·봇체크·에러) 또는 렌더 실패
                else:
                    fail += 1   # 빈 화면(단색)
            if (done + junk + fail) % 25 == 0:
                print(f"  진행 {done + junk + fail}/{len(targets)} … ✅{done} 정크/실패{junk + fail}")

        chunk = _SCREENSHOT_CONCURRENCY * 3
        for s in range(0, len(targets), chunk):
            await asyncio.gather(*(one(m) for m in targets[s:s + chunk]))

    print("-" * 56)
    print(f"✅ 스크린샷 {done} · 정크게이트 {junk} · 빈/실패 {fail}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="대표 이미지(thumbnail_url) 백필 v2")
    ap.add_argument("--mode", choices=("kakao", "screenshot", "both"), default="kakao")
    ap.add_argument("--sigungu", default="강남구")
    ap.add_argument("--force", action="store_true", help="이미 thumbnail 있어도 재계산")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    db = DynamoAdapter()
    s3 = S3Adapter()
    metas = db.list_hospitals_by_sigungu(args.sigungu)
    if args.limit:
        metas = metas[: args.limit]
    print(f"대상: {args.sigungu} {len(metas)}곳  mode={args.mode} force={args.force} dry={args.dry_run}")
    print("-" * 56)

    if args.mode in ("kakao", "both"):
        run_kakao(db, metas, args.force, args.dry_run)
        if args.mode == "both":
            # kakao 단계가 thumbnail 을 채웠으니 최신 상태로 다시 로드(스크린샷 대상 재판정).
            metas = db.list_hospitals_by_sigungu(args.sigungu)
            if args.limit:
                metas = metas[: args.limit]
    if args.mode in ("screenshot", "both"):
        asyncio.run(run_screenshots(db, s3, metas, args.force, args.dry_run))


if __name__ == "__main__":
    main()
