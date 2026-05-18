"""변경 감지(diff) 로직 — 재크롤링 시 변경 여부 판단."""

from __future__ import annotations

from shared.models import CrawlData


def has_significant_change(old: CrawlData, new: CrawlData) -> bool:
    """두 크롤링 결과 비교. 유의미한 변경이 있으면 True."""
    if not old.pages or not new.pages:
        return True

    # 페이지 수 변화
    if abs(len(old.pages) - len(new.pages)) > 2:
        return True

    # 메인 페이지 텍스트 변화율
    old_main = next((p for p in old.pages if p.page_type == "main"), None)
    new_main = next((p for p in new.pages if p.page_type == "main"), None)

    if old_main and new_main:
        similarity = _text_similarity(old_main.html_text, new_main.html_text)
        if similarity < 0.85:  # 15% 이상 변경
            return True

    # 이미지 수 변화
    if abs(len(old.images) - len(new.images)) > 5:
        return True

    return False


def _text_similarity(text_a: str, text_b: str) -> float:
    """간단한 텍스트 유사도 (단어 집합 기반 Jaccard)."""
    words_a = set(text_a.split())
    words_b = set(text_b.split())

    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union)
