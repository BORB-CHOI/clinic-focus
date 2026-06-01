"""shared/etc_category.py — 기타 하위 카테고리 파생 테스트."""
from shared.etc_category import derive_etc_subcategory, display_specialty


def test_single_focus_maps_to_category():
    assert derive_etc_subcategory(["모발·탈모"]) == "모발·탈모"
    assert derive_etc_subcategory(["코골이·수면무호흡"]) == "수면"
    assert derive_etc_subcategory(["우울·불안"]) == "정신"


def test_priority_specialist_beats_cosmetic():
    # 미용 신호가 섞여도 특이성 높은 전문 신호가 이긴다(미용은 우선순위 최하위)
    assert derive_etc_subcategory(["리프팅·탄력", "보톡스·필러", "모발·탈모"]) == "모발·탈모"
    assert derive_etc_subcategory(["보톡스·필러", "통증재활", "척추·디스크"]) == "통증·근골격"
    assert derive_etc_subcategory(["기미·색소", "우울·불안"]) == "정신"


def test_cosmetic_only_stays_cosmetic():
    assert derive_etc_subcategory(["리프팅·탄력", "보톡스·필러", "기미·색소"]) == "미용"


def test_empty_or_unknown_fallback_to_general():
    assert derive_etc_subcategory([]) == "일반"
    assert derive_etc_subcategory(None) == "일반"
    assert derive_etc_subcategory(["존재하지않는토큰"]) == "일반"


def test_display_specialty_only_rewrites_etc():
    # 표준 진료과목은 불변, '기타'만 파생 카테고리로 치환
    assert display_specialty("피부과", ["여드름"]) == "피부과"
    assert display_specialty("치과", ["임플란트"]) == "치과"
    assert display_specialty("기타", ["모발·탈모"]) == "모발·탈모"
    assert display_specialty("기타", []) == "일반"
    assert display_specialty(None, None) == "기타"
