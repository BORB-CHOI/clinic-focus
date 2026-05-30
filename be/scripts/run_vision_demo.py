"""Vision 시연 배치 — 시연 10개 병원 대상 이미지 분석 + DDB VISION#RESULTS 적재.

이 스크립트는 **1만 베이스라인 배치(run_classification.py)와 완전히 분리**된
별도 실행 경로다. run_index_pipeline(demo=False) 에서는 절대 실행되지 않는다.

목적:
  1. Sonnet 4.6(개인 계정)으로 병원 이미지를 Vision 분석 — 비용이 크므로 1회 실행 후 재사용.
  2. 결과를 DDB VISION#RESULTS entity 에 put_entity 로 적재.
  3. 이후 run_index_pipeline(demo=True) 또는 run_index_pipeline(demo=False) 에서
     DDB VISION#RESULTS 를 로드해 KB vision 청크로 편입한다.

동작 흐름:
  1. DDB META 에서 hospital_id 목록 조회 → 최대 MAX_LLM_DEMO_HOSPITALS(기본 10)개 처리.
  2. S3 load_crawl_data 로 CrawlData 로드 → crawl_data.images[*].url 수집.
  3. analyze_images(image_urls) 호출 (MAX_VISION_IMAGES 준수, 개인 계정 Sonnet 4.6 사용).
  4. 결과를 DDB put_entity(hospital_id, "VISION#RESULTS", {"results": [...]}) 로 저장.
  5. 이미 VISION#RESULTS 가 있으면 건너뜀 (--force 플래그로 덮어쓰기 가능).

비용 주의:
  Sonnet 4.6 Vision 호출은 이미지당 ~$0.01~0.04. 10개 병원 × 최대 10장 = 최대 100회 호출.
  반드시 MAX_VISION_IMAGES 환경변수로 이미지 수를 조절할 것.

실행:
  .venv/bin/python be/scripts/run_vision_demo.py [--force] [--hospital-ids ID1 ID2 ...]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# 프로젝트 루트를 sys.path 에 추가 (EC2 실행 경로 독립성)
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

from dotenv import load_dotenv  # type: ignore[import-untyped]

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


def _load_demo_hospital_ids(db, explicit_ids: list[str] | None) -> list[str]:
    """시연 대상 hospital_id 목록 반환.

    explicit_ids 가 주어지면 그대로 사용.
    없으면 DDB META 순회 → 최대 MAX_LLM_DEMO_HOSPITALS 개.
    """
    max_demo = int(os.environ.get("MAX_LLM_DEMO_HOSPITALS", "10"))

    if explicit_ids:
        return explicit_ids[:max_demo]

    ids: list[str] = []
    for hid in db.iter_all_hospital_ids():
        ids.append(hid)
        if len(ids) >= max_demo:
            break
    return ids


def run_vision_demo(
    hospital_ids: list[str] | None = None,
    *,
    force: bool = False,
) -> dict:
    """Vision 시연 배치 실행.

    Args:
        hospital_ids: 처리할 병원 ID 목록. None 이면 DDB META 에서 MAX_LLM_DEMO_HOSPITALS 개.
        force: True 면 기존 VISION#RESULTS 가 있어도 덮어씀.

    Returns:
        {"success": N, "skipped": N, "failed": N, "hospital_ids": [...]} 요약 dict.
    """
    from be.adapters.dynamo_adapter import DynamoAdapter
    from be.adapters.s3_adapter import S3Adapter
    from ai.pipeline.vision import analyze_images

    db = DynamoAdapter()
    s3 = S3Adapter()

    target_ids = _load_demo_hospital_ids(db, hospital_ids)
    logger.info("Vision 시연 배치 시작 — 대상 %d개 병원", len(target_ids))

    results_summary: dict = {
        "success": 0,
        "skipped": 0,
        "failed": 0,
        "hospital_ids": [],
    }

    for hospital_id in target_ids:
        logger.info("[%s] 처리 시작", hospital_id)

        # 기존 결과 확인 — force=False 면 건너뜀
        if not force:
            existing = db.get_entity(hospital_id, "VISION#RESULTS")
            if existing:
                logger.info("[%s] VISION#RESULTS 기존 결과 존재 → 건너뜀 (--force 로 덮어쓰기 가능)", hospital_id)
                results_summary["skipped"] += 1
                continue

        # CrawlData 로드
        crawl_data = s3.load_crawl_data(hospital_id)
        if not crawl_data:
            logger.warning("[%s] CrawlData 없음 — 건너뜀", hospital_id)
            results_summary["failed"] += 1
            continue

        # 이미지 URL 수집 (S3 URI 또는 https URL)
        image_urls = [img.url for img in (crawl_data.images or []) if img.url]
        if not image_urls:
            logger.info("[%s] 이미지 없음 — 빈 결과 적재", hospital_id)
            db.put_entity(hospital_id, "VISION#RESULTS", {"results": []})
            results_summary["skipped"] += 1
            continue

        max_images = int(os.environ.get("MAX_VISION_IMAGES", "10"))
        if len(image_urls) > max_images:
            logger.info(
                "[%s] 이미지 %d장 중 MAX_VISION_IMAGES=%d 제한으로 앞에서 %d장만 분석",
                hospital_id, len(image_urls), max_images, max_images,
            )
            image_urls = image_urls[:max_images]

        # Vision 분석 — 개인 계정 Sonnet 4.6 호출 (비용 발생)
        try:
            analysis_results = analyze_images(image_urls)
        except Exception as exc:
            logger.error("[%s] analyze_images 실패: %s", hospital_id, exc)
            results_summary["failed"] += 1
            continue

        # 결과를 JSON 직렬화 가능한 형태로 변환
        serialized = []
        for r in analysis_results:
            dump = getattr(r, "model_dump", None)
            if callable(dump):
                serialized.append(dump())
            elif isinstance(r, dict):
                serialized.append(r)
            else:
                serialized.append(json.loads(json.dumps(r, default=str)))

        # DDB VISION#RESULTS 적재
        db.put_entity(hospital_id, "VISION#RESULTS", {"results": serialized})
        logger.info(
            "[%s] VISION#RESULTS 적재 완료 — %d장 분석",
            hospital_id, len(serialized),
        )

        results_summary["success"] += 1
        results_summary["hospital_ids"].append(hospital_id)

    logger.info(
        "Vision 시연 배치 완료 — 성공 %d / 건너뜀 %d / 실패 %d",
        results_summary["success"],
        results_summary["skipped"],
        results_summary["failed"],
    )
    return results_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vision 시연 배치 — 시연 10개 병원 이미지 분석 + DDB VISION#RESULTS 적재"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="기존 VISION#RESULTS 가 있어도 덮어씀",
    )
    parser.add_argument(
        "--hospital-ids",
        nargs="+",
        metavar="ID",
        help="분석할 hospital_id 목록 (미지정 시 DDB META 에서 MAX_LLM_DEMO_HOSPITALS 개)",
    )
    args = parser.parse_args()

    summary = run_vision_demo(
        hospital_ids=args.hospital_ids or None,
        force=args.force,
    )

    print("\n" + "=" * 60)
    print("Vision 시연 배치 결과")
    print("=" * 60)
    print(f"  성공: {summary['success']}개")
    print(f"  건너뜀: {summary['skipped']}개")
    print(f"  실패: {summary['failed']}개")
    if summary["hospital_ids"]:
        print(f"  처리 완료 ID: {', '.join(summary['hospital_ids'])}")


if __name__ == "__main__":
    main()
