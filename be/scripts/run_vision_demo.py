"""Vision 시연 배치 (트랙 C) — 하이브리드 이미지 획득 + DDB VISION#RESULTS 적재.

이 스크립트는 **1만 베이스라인 배치(run_classification.py)와 완전히 분리**된
별도 실행 경로다. run_index_pipeline(demo=False) 에서는 절대 실행되지 않는다.

## 왜 하이브리드인가 (구 방식이 망한 이유)

구 방식은 crawl_data.images 의 **`<img>` 태그 URL만** Vision 에 넣었다. 그런데 그
URL 들은 대부분 로고·히어로배너라 Vision 이 "기타/건물"로만 보고 vision=0 →
아무 병원도 "확실"이 안 됐다. 진짜 시술사진·전후비교·장비·이미지에 박힌 텍스트·
CSS 배경·팝업은 `<img>` 로 안 잡힌다.

그래서:
  1. **스크린샷(주력)** — `screenshot_page_scroll` 로 페이지를 위→아래 뷰포트 타일로
     전부 캡처. 렌더된 화면 그대로라 위의 것들이 다 잡힌다. Vision 이 글자만 읽는 게
     아니라 **장면을 해석**(scene·detected_procedures·in_image_text)한다.
  2. **`<img>`(보조)** — 슬라이더/캐러셀은 스크린샷이 현재 슬라이드만 잡으므로
     `filter_content_image_urls` 로 로고·배너를 걷어낸 콘텐츠 이미지로 보완.

## 동작 흐름

  1. 대상 선정 — 기본은 **강남구 무작위 N개**(크롤 완료 ∧ website_url 보유 풀에서).
     --hospital-ids 로 명시 지정 가능.
  2. 각 병원: website_url → screenshot_page_scroll(타일 bytes) + filter <img> URL.
     예산(MAX_VISION_IMAGES) 안에서 스크린샷 우선 + img 보조로 분배.
  3. analyze_screenshots(bytes) + analyze_images(filtered urls) → ImageAnalysisResult.
  4. DDB put_entity(hospital_id, "VISION#RESULTS", {"results": [...]}).
  5. 이미 VISION#RESULTS 있으면 건너뜀 (--force 로 덮어쓰기).

이후 run_llm_demo.py(또는 run_index_pipeline demo=True)가 VISION#RESULTS 를 로드해
4축 교차검증·KB vision 청크에 편입한다.

## 비용·시간 주의

  Sonnet 4.6 Vision 호출은 이미지당 ~$0.01~0.02. 병원당 ~6~10장(스크린샷+img).
  무작위 100개면 ~$10~20 + 시간 ~수십분(스크린샷 캡처·Vision 호출 모두 순차).
  MAX_VISION_IMAGES / --max-tiles / --img-supplement 로 장수를 조절할 것.

## 실행

  .venv/bin/python be/scripts/run_vision_demo.py                 # 강남 무작위 10(기본)
  .venv/bin/python be/scripts/run_vision_demo.py --sample 100    # 강남 무작위 100
  .venv/bin/python be/scripts/run_vision_demo.py --hospital-ids ID1 ID2 [--force]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys

# 프로젝트 루트를 sys.path 에 추가 (EC2 실행 경로 독립성)
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

from dotenv import load_dotenv  # type: ignore[import-untyped]  # noqa: E402

load_dotenv(
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("run_vision_demo")

_DEFAULT_MAX_TILES = 5        # 스크린샷 최대 타일 수 (위→아래). 7→5: 속도·브라우저부하↓
_DEFAULT_IMG_SUPPLEMENT = 2   # <img> 보조 최대 장수 (슬라이더/갤러리 보완)


# ---------------------------------------------------------------------------
# 대상 선정
# ---------------------------------------------------------------------------

def _crawled_ids() -> set[str]:
    """S3 crawl/ 에 crawl_data.json 이 있는 병원 id 집합 (=크롤 완료)."""
    import boto3
    s3 = boto3.client("s3", os.environ.get("AWS_REGION", "us-east-1"))
    bucket = os.environ["S3_CRAWL_BUCKET"]
    ids: set[str] = set()
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="crawl/"):
        for o in pg.get("Contents", []):
            if o["Key"].endswith("crawl_data.json"):
                ids.add(o["Key"].split("/")[1])
    return ids


def _select_random(sigungu: str, n: int, seed: int) -> list[str]:
    """sigungu 의 병원 중 (크롤 완료 ∧ website_url 보유) 풀에서 무작위 N개.

    Vision 은 website_url 의 화면을 캡처하므로 URL 이 있어야 하고, 4축 교차검증
    텍스트가 있어야 하므로 크롤도 완료돼 있어야 한다. 둘 다 만족하는 풀에서 추출.
    """
    import boto3
    from boto3.dynamodb.conditions import Attr
    t = boto3.resource("dynamodb", os.environ.get("AWS_REGION", "us-east-1")).Table(
        os.environ["DYNAMO_TABLE"]
    )
    crawled = _crawled_ids()

    eligible: list[str] = []
    lek = None
    while True:
        kw = dict(
            FilterExpression=Attr("entity").eq("META") & Attr("sigungu").eq(sigungu),
            ProjectionExpression="hospital_id, contact",
        )
        if lek:
            kw["ExclusiveStartKey"] = lek
        r = t.scan(**kw)
        for it in r["Items"]:
            url = (it.get("contact") or {}).get("website_url") or ""
            if url.strip() and it["hospital_id"] in crawled:
                eligible.append(it["hospital_id"])
        lek = r.get("LastEvaluatedKey")
        if not lek:
            break

    logger.info("선정 풀: %s 크롤완료∧URL보유 %d개 → 무작위 %d개 (seed=%d)",
                sigungu, len(eligible), min(n, len(eligible)), seed)
    rng = random.Random(seed)
    rng.shuffle(eligible)
    return eligible[:n]


# ---------------------------------------------------------------------------
# 하이브리드 이미지 획득 + 분석
# ---------------------------------------------------------------------------

def _split_budget(n_shots: int, n_imgs: int, max_total: int, img_supplement: int) -> tuple[int, int]:
    """예산(max_total) 안에서 스크린샷 우선·img 보조로 장수 분배.

    스크린샷이 0장(URL 실패 등)이어도 img 는 보조 상한(img_supplement)까지만 —
    스크린샷 실패한 사이트에 10장씩 Vision 호출하는 낭비를 막는다(구 버그).
    """
    if n_shots == 0:
        return 0, min(n_imgs, img_supplement)
    img_take = min(n_imgs, img_supplement, max(0, max_total - 1))  # 최소 스크린샷 1칸 확보
    shot_take = min(n_shots, max_total - img_take)
    return shot_take, img_take


async def _process_one(bm, db, s3, hospital_id: str, *, force: bool,
                       max_tiles: int, img_supplement: int) -> str:
    """병원 1개 처리 → 상태 문자열("ok"/"skip"/"fail") 반환.

    스크린샷 타일 + 필터된 `<img>` 를 **한 번의 Vision 호출(analyze_batch)** 로 종합 →
    이미지당 1콜(순차 ~8초×N) 대비 병원당 수십 초 절감.
    """
    from ai.pipeline.vision import (
        analyze_batch,
        download_content_images,
        filter_content_image_urls,
    )

    if not force and db.get_entity(hospital_id, "VISION#RESULTS"):
        logger.info("[%s] VISION#RESULTS 존재 → 건너뜀(--force 로 덮어쓰기)", hospital_id[:12])
        return "skip"

    crawl_data = s3.load_crawl_data(hospital_id)
    if not crawl_data:
        logger.warning("[%s] CrawlData 없음 — 건너뜀", hospital_id[:12])
        return "fail"

    url = (crawl_data.website_url or "").strip()
    max_total = int(os.environ.get("MAX_VISION_IMAGES", "10"))

    # 1) 스크린샷(주력) — 위→아래 타일 캡처
    shots: list[bytes] = []
    if url:
        try:
            shots = await bm.screenshot_page_scroll(url, max_tiles=max_tiles)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] 스크린샷 실패(%s) — img 보조만 사용", hospital_id[:12], exc)

    # 2) <img>(보조) — 로고·배너 필터 후 콘텐츠 이미지만
    raw_img_urls = [i.url for i in (crawl_data.images or []) if i.url]
    img_urls = filter_content_image_urls(raw_img_urls)

    shot_take, img_take = _split_budget(len(shots), len(img_urls), max_total, img_supplement)

    # 3) 이미지 bytes 한 묶음으로 모으기: 스크린샷(png) + img 다운로드(핫링크/HTML 스킵)
    images: list[tuple[bytes, str]] = [(b, "image/png") for b in shots[:shot_take] if b]
    if img_take:
        images += download_content_images(img_urls[:img_take])

    if not images:
        logger.info("[%s] 분석할 이미지 없음 — 빈 결과 적재", hospital_id[:12])
        db.put_entity(hospital_id, "VISION#RESULTS", {"results": []})
        return "skip"

    # 4) Vision 분석 (장면 해석) — 한 번의 멀티이미지 호출로 종합
    try:
        result = analyze_batch(images, label=hospital_id[:8])
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] Vision 분석 실패: %s", hospital_id[:12], exc)
        return "fail"
    if result is None:
        db.put_entity(hospital_id, "VISION#RESULTS", {"results": []})
        return "skip"

    # 5) 적재 (배치 결과 1건)
    db.put_entity(hospital_id, "VISION#RESULTS", {"results": [result.model_dump()]})
    logger.info("[%s] 적재 — 스크린샷%d+img%d=%d장 1콜 | 시술=%s 기기=%s",
                hospital_id[:12], shot_take, len(images) - shot_take, len(images),
                (result.detected_procedures or [])[:6], (result.detected_devices or [])[:6])
    return "ok"


async def run_vision_demo_async(hospital_ids: list[str], *, force: bool,
                                max_tiles: int, img_supplement: int) -> dict:
    from be.adapters.dynamo_adapter import DynamoAdapter
    from be.adapters.s3_adapter import S3Adapter
    from be.core.browser_manager import BrowserManager

    db = DynamoAdapter()
    s3 = S3Adapter()
    summary = {"ok": 0, "skip": 0, "fail": 0, "total": len(hospital_ids)}

    async with BrowserManager() as bm:
        for i, hid in enumerate(hospital_ids, 1):
            logger.info("───── [%d/%d] %s ─────", i, len(hospital_ids), hid[:16])
            try:
                status = await _process_one(
                    bm, db, s3, hid, force=force,
                    max_tiles=max_tiles, img_supplement=img_supplement,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[%s] 처리 중 예외: %s", hid[:12], exc)
                status = "fail"
            summary[status] += 1

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Vision 시연 배치 (트랙 C) — 하이브리드 스크린샷+img")
    ap.add_argument("--hospital-ids", nargs="+", metavar="ID",
                    help="명시 대상 (생략 시 강남 무작위 --sample 개)")
    ap.add_argument("--sample", type=int, default=int(os.environ.get("MAX_LLM_DEMO_HOSPITALS", "10")),
                    help="무작위 표본 수 (기본 MAX_LLM_DEMO_HOSPITALS)")
    ap.add_argument("--sigungu", default="강남구", help="대상 시군구 (기본 강남구 — PoC)")
    ap.add_argument("--seed", type=int, default=42, help="무작위 시드 (재현용)")
    ap.add_argument("--max-tiles", type=int, default=_DEFAULT_MAX_TILES, help="스크린샷 최대 타일 수")
    ap.add_argument("--img-supplement", type=int, default=_DEFAULT_IMG_SUPPLEMENT, help="<img> 보조 최대 장수")
    ap.add_argument("--force", action="store_true", help="기존 VISION#RESULTS 덮어쓰기")
    args = ap.parse_args(argv)

    if args.hospital_ids:
        target_ids = args.hospital_ids
    else:
        target_ids = _select_random(args.sigungu, args.sample, args.seed)

    print(f"{'='*60}\nVision 시연 배치 (하이브리드) — 대상 {len(target_ids)}개\n"
          f"  스크린샷 최대 {args.max_tiles}타일 + img 보조 최대 {args.img_supplement}장 "
          f"(예산 MAX_VISION_IMAGES={os.environ.get('MAX_VISION_IMAGES','10')})\n{'='*60}")

    summary = asyncio.run(run_vision_demo_async(
        target_ids, force=args.force,
        max_tiles=args.max_tiles, img_supplement=args.img_supplement,
    ))

    print(f"\n{'='*60}\nVision 시연 배치 결과")
    print(f"  ✅ 성공 {summary['ok']} / ⏭️ 건너뜀 {summary['skip']} / ❌ 실패 {summary['fail']} "
          f"(전체 {summary['total']})")
    print('='*60)


if __name__ == "__main__":
    main()
