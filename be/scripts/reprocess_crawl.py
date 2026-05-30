"""기존 자체사이트 crawl_data 재처리 — denoise + 페이지 노이즈 필터 적용 후 S3 적재.

배경: BE 담당자 크롤(be/data/crawl, 2133)은 페이지 단위 노이즈(RSS 아카이브 덤프·에러/
준비중·중복 페이지)가 남아 있고 S3 엔 옛 848 만 있다. 이 스크립트는 **재크롤 없이**(본문은
이미 추출돼 있으므로) crawler 의 정제 함수를 그대로 적용해 깨끗한 crawl_data 를 S3 에 올린다.

  로컬 be/data/crawl/{id}/crawl_data.json
    → CrawlData 검증
    → _denoise_pages (단락 정제, 이슈 #13)
    → _filter_noise_pages (페이지 단위: 에러/준비중 제외·중복 제거·블로그 RSS 캡)
    → S3 crawl/{id}/crawl_data.json (--confirm)

크롤러(crawl_one_hospital)와 **같은 함수**를 쓰므로 로직 중복 없음 — 미래 크롤은 크롤 시
자동 정제, 기존 데이터는 이 1회성 러너로 동일 정제. 네트워크 없음(S3 put 만).

실행: .venv/bin/python be/scripts/reprocess_crawl.py [--src be/data/crawl] [--confirm]
  --confirm 없으면 dry-run (S3 미적재, 정제 통계만).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from be.core.crawler import _denoise_pages, _filter_noise_pages  # noqa: E402
from shared.models import CrawlData  # noqa: E402


def reprocess(data: CrawlData) -> CrawlData:
    """crawler 와 동일한 정제 파이프라인을 기존 CrawlData 에 적용."""
    cleaned_pages = _filter_noise_pages(_denoise_pages(list(data.pages)))
    return data.model_copy(update={"pages": cleaned_pages})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="기존 crawl_data 재처리(denoise+페이지필터) → S3")
    ap.add_argument("--src", default="be/data/crawl", help="로컬 crawl_data 폴더")
    ap.add_argument("--confirm", action="store_true", help="지정 시 S3 적재. 미지정=dry-run")
    ap.add_argument("--limit", type=int, default=0, help="처리 개수 제한(0=전체, 디버그용)")
    args = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.src, "*", "crawl_data.json")))
    if args.limit:
        files = files[:args.limit]
    if not files:
        print(f"crawl_data 없음: {args.src}")
        return

    s3 = None
    if args.confirm:
        from be.adapters.s3_adapter import S3Adapter
        s3 = S3Adapter()

    mode = "CONFIRM (S3 적재)" if args.confirm else "DRY-RUN (통계만)"
    print(f"{'='*58}\n자체사이트 재처리 — {mode} | {len(files)}개\n{'='*58}")

    pg_before = pg_after = txt_before = txt_after = 0
    blog_before = blog_after = saved = errs = 0

    for i, f in enumerate(files, 1):
        try:
            cd = CrawlData(**json.load(open(f, encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            errs += 1
            print(f"  ⚠️ 검증 실패 {os.path.basename(os.path.dirname(f))}: {str(e)[:80]}")
            continue

        b_pages = len(cd.pages)
        b_txt = sum(len(p.html_text or "") for p in cd.pages)
        b_blog = sum(1 for p in cd.pages if p.page_type == "blog")

        cleaned = reprocess(cd)
        a_pages = len(cleaned.pages)
        a_txt = sum(len(p.html_text or "") for p in cleaned.pages)
        a_blog = sum(1 for p in cleaned.pages if p.page_type == "blog")

        pg_before += b_pages; pg_after += a_pages
        txt_before += b_txt; txt_after += a_txt
        blog_before += b_blog; blog_after += a_blog

        if args.confirm:
            s3.save_crawl_data(cleaned.hospital_id, cleaned)
            saved += 1

        if i % 200 == 0:
            print(f"  [{i}/{len(files)}] 페이지 {pg_before}→{pg_after} | 저장 {saved}")

    def pct(a, b):
        return f"{(b-a)/b*100:.0f}%↓" if b else "—"

    print(f"\n{'='*58}")
    print(f"  처리:        {len(files)}개 (검증실패 {errs})")
    print(f"  페이지:      {pg_before:,} → {pg_after:,}  ({pct(pg_after, pg_before)})")
    print(f"    └ blog:    {blog_before:,} → {blog_after:,}  ({pct(blog_after, blog_before)}, RSS 아카이브 캡)")
    print(f"  본문 글자:   {txt_before:,} → {txt_after:,}  ({pct(txt_after, txt_before)})")
    if args.confirm:
        print(f"  S3 적재:     {saved}개 (crawl/{{id}}/crawl_data.json)")
    else:
        print(f"  DRY-RUN — --confirm 시 {len(files)-errs}개 S3 적재 예정")
    print('='*58)


if __name__ == "__main__":
    main()
