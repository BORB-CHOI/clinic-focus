"""crawl_external_all.py — 외부 플랫폼 시그널 일괄 크롤 (카카오 place-api + 구글 Places).

한 병원당:
  1. 카카오 공식 dapi 검색(`KakaoAdapter`)으로 place_id 획득
  2. 카카오 place-api panel3/reviews/blog httpx 단발 → parse → KAKAO#PLACE/REVIEWS/BLOG
  3. 구글 Places (New) Text Search → Details(reviews 5) → parse → GOOGLE#PLACE
  4. DDB 적재 (DynamoAdapter.put_entity, entity SK = KAKAO#PLACE 등)

⚠️ 회색지대 — 실행 정책 미확정 (절대 임의 실행 금지)
  카카오 place-api.map.kakao.com 은 robots.txt 자동화 금지 + 약관 비정상 접근 금지
  대상이다(task-queue.md Phase B 사실 13~24). 구글 Places 는 공식 API 라 합법.
  **실제 1,084개 일괄 실행 여부는 사용자(운영자) 결정 사항**이다. 이 스크립트는:
    - 기본 dry-run: --confirm 없으면 네트워크 호출 0건, 대상 목록만 출력
    - --confirm 줘야 실제 fetch. 그래도 카카오 부분은 회색지대 경고를 먼저 찍는다
    - --source 로 google 만 돌리면 합법 범위로 한정 가능

사용 예:
    # dry-run (대상 카운트만)
    .venv/bin/python -m be.scripts.crawl_external_all
    # 구글만 실제 실행 (합법)
    .venv/bin/python -m be.scripts.crawl_external_all --confirm --source google --limit 10
    # 전체 (카카오 포함 — 회색지대, 운영자 책임)
    .venv/bin/python -m be.scripts.crawl_external_all --confirm --source all

의료법 §56③: 후기·블로그 본문 raw 는 DDB 저장·임베딩 입력으로만. parse_* 가 PII 제거.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from be.scripts._utils import load_env

logger = logging.getLogger("crawl_external_all")

# 회색지대 경고 — 카카오 place-api 실행 전 반드시 출력
_KAKAO_GRAYZONE_WARNING = (
    "\n[경고] 카카오 place-api.map.kakao.com 은 robots.txt 자동화 금지 + 약관\n"
    "       비정상 접근 금지 대상입니다 (task-queue.md 사실 13~24).\n"
    "       1만 풀커버 rate-limit 미실측. 실행 책임은 운영자에게 있습니다.\n"
    "       합법 범위만 원하면 --source google 로 한정하세요.\n"
)

# 카카오 place-api 호출 간 지연(초) — rate-limit 회피 (실측 전 보수적 기본값)
_KAKAO_DELAY_SEC = 1.5
_GOOGLE_DELAY_SEC = 0.2


def _iter_targets(dynamo, limit: int | None) -> list[tuple[str, str, str]]:
    """대상 (hospital_id, name, address) 목록. META 에서 추출."""
    targets: list[tuple[str, str, str]] = []
    for hid in dynamo.iter_all_hospital_ids():
        meta = dynamo.load_hospital_meta(hid)
        if meta is None:
            continue
        if not meta.location.address:
            # 주소 없으면 검색 매칭 정확도가 떨어져 스킵 (이름만으로는 동명 병원 오매칭)
            logger.info("주소 누락 — 외부 시그널 스킵: %s (%s)", meta.name, hid)
            continue
        targets.append((hid, meta.name, meta.location.address))
        if limit is not None and len(targets) >= limit:
            break
    return targets


def _crawl_kakao_one(hospital_id: str, name: str, address: str, dynamo) -> bool:
    """한 병원 카카오 시그널 fetch→parse→DDB 적재. 성공 시 True.

    공식 dapi 로 place_id 획득 후 비공식 place-api 3 호출.
    """
    from be.adapters.kakao_adapter import KakaoAdapter
    from be.adapters.kakao_place_adapter import (
        KakaoPlaceAdapter,
        parse_blog,
        parse_place,
        parse_reviews,
    )

    official = KakaoAdapter()
    info = official.get_hospital_info(name, address)
    place_id = str(info.get("kakao_id") or "")
    if not place_id:
        logger.info("카카오 매칭 실패: %s (%s)", name, hospital_id)
        return False

    with KakaoPlaceAdapter() as adapter:
        panel3 = adapter.fetch_panel3(place_id)
        if panel3 is None:
            logger.info("카카오 panel3 없음: %s place_id=%s", name, place_id)
            return False
        dynamo.put_entity(hospital_id, "KAKAO#PLACE", parse_place(panel3, place_id))

        reviews_json = adapter.fetch_reviews(place_id)
        if reviews_json is not None:
            dynamo.put_entity(hospital_id, "KAKAO#REVIEWS", parse_reviews(reviews_json))

        blog_json = adapter.fetch_blog(place_id)
        if blog_json is not None:
            dynamo.put_entity(hospital_id, "KAKAO#BLOG", parse_blog(blog_json))
    return True


def _crawl_google_one(hospital_id: str, name: str, address: str, dynamo) -> bool:
    """한 병원 구글 Places fetch→parse→DDB 적재. 성공 시 True (공식 API)."""
    from be.adapters.google_places_adapter import (
        GooglePlacesAdapter,
        parse_google_reviews,
    )

    with GooglePlacesAdapter() as adapter:
        place_id = adapter.search_place_id(name, address)
        if not place_id:
            logger.info("구글 매칭 실패: %s (%s)", name, hospital_id)
            return False
        details = adapter.fetch_details(place_id)
        if details is None:
            return False
        dynamo.put_entity(hospital_id, "GOOGLE#PLACE", parse_google_reviews(details))
    return True


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="외부 플랫폼 시그널 일괄 크롤")
    parser.add_argument(
        "--confirm", action="store_true",
        help="실제 네트워크 호출 + DDB 적재. 미지정 시 dry-run (대상 목록만).",
    )
    parser.add_argument(
        "--source", choices=["all", "kakao", "google"], default="all",
        help="크롤 대상 소스. google 만 = 합법 범위 한정.",
    )
    parser.add_argument("--limit", type=int, default=None, help="대상 병원 수 제한 (테스트용)")
    args = parser.parse_args(argv)

    load_env()
    from be.adapters.dynamo_adapter import DynamoAdapter

    dynamo = DynamoAdapter()
    targets = _iter_targets(dynamo, args.limit)
    logger.info("대상 병원 %d개 (source=%s)", len(targets), args.source)

    if not args.confirm:
        logger.info(
            "\n[dry-run] --confirm 미지정 — 네트워크 호출 안 함. 대상 목록 상위 5개:"
        )
        for hid, name, addr in targets[:5]:
            logger.info("  - %s | %s | %s", hid, name, addr)
        logger.info(
            "\n실제 실행하려면 --confirm 추가. 카카오 포함 시 회색지대 경고 확인 필요."
        )
        return 0

    do_kakao = args.source in ("all", "kakao")
    do_google = args.source in ("all", "google")

    if do_kakao:
        logger.warning(_KAKAO_GRAYZONE_WARNING)

    kakao_ok = google_ok = 0
    for hid, name, addr in targets:
        if do_kakao:
            if _crawl_kakao_one(hid, name, addr, dynamo):
                kakao_ok += 1
            time.sleep(_KAKAO_DELAY_SEC)
        if do_google:
            if _crawl_google_one(hid, name, addr, dynamo):
                google_ok += 1
            time.sleep(_GOOGLE_DELAY_SEC)

    logger.info(
        "\n완료 — 카카오 적재 %d / 구글 적재 %d (대상 %d)",
        kakao_ok, google_ok, len(targets),
    )
    logger.info(
        "후속: be.scripts.run_classification 으로 외부 시그널 포함 재분류 + KB ingest."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
