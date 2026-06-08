"""shared/etc_category.py — 기타 하위 카테고리 파생 테스트."""
from shared.etc_category import derive_etc_subcategory, display_specialty


def test_single_focus_maps_to_category():
    assert derive_etc_subcategory(["모발·탈모"]) == "모발·탈모"
    assert derive_etc_subcategory(["코골이·수면무호흡"]) == "수면"
    assert derive_etc_subcategory(["우울·불안"]) == "정신"


def test_prominence_wins_over_priority():
    # primary_focus 는 주력 강도 내림차순 — 주력 가중치가 높은 카테고리가 이긴다.
    # 리프팅(미용)이 주력이고 탈모는 말단이면 '미용'. (예전 버그: 순위만 보고 '모발·탈모')
    assert derive_etc_subcategory(["리프팅·탄력", "보톡스·필러", "모발·탈모"]) == "미용"
    # 탈모가 주력이면 그대로 '모발·탈모' — 진짜 탈모 의원은 보존.
    assert derive_etc_subcategory(["모발·탈모", "한방피부·미용"]) == "모발·탈모"
    # 기미가 주력(가중치 2) > 우울(가중치 1) → '미용'.
    assert derive_etc_subcategory(["기미·색소", "우울·불안"]) == "미용"


def test_tie_breaks_to_specialist():
    # 미용 3(보톡스 첫토큰) = 통증 3(통증재활 2 + 척추 1) 동점 → 특이성 높은 통증·근골격.
    assert derive_etc_subcategory(["보톡스·필러", "통증재활", "척추·디스크"]) == "통증·근골격"


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
