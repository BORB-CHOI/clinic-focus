"""_scrub_ad_phrases 단위 테스트 — 의료광고(§56) 표현 임베딩 스크럽."""

from ai.search.kb_store import _scrub_ad_phrases


# ── STRONG (자칭) — 명백 위반 제거, 의료 명사·합법어 보존 ──────────────
def test_strong_removes_clear_violations():
    src = "22년간 한 건의 사고 없이 안전한 진료를 실시. 무통 시술, 완치 보장, 부작용 없는 수술."
    out = _scrub_ad_phrases(src, aggressive=True)
    for bad in ["무통", "완치", "안전한"]:
        assert bad not in out, f"{bad} 미제거: {out}"
    # 의료 명사는 보존
    assert "진료" in out and "수술" in out and "시술" in out


def test_strong_removes_superiority_words():
    src = "국내 최고 명의가 운영하는 독보적인 프리미엄 명품 성형, 강남 1위, 베스트 클리닉"
    out = _scrub_ad_phrases(src, aggressive=True)
    for bad in ["최고", "명의", "독보적", "프리미엄", "명품", "1위", "베스트"]:
        assert bad not in out, f"{bad} 미제거: {out}"


def test_strong_keeps_jeonmun_legal():
    """'전문/전문의/전문병원'은 합법 사실 용어 — 절대 제거 안 함."""
    src = "피부과 전문의가 진료하는 전문병원, 양악수술 전문"
    out = _scrub_ad_phrases(src, aggressive=True)
    assert "전문의" in out and "전문병원" in out and "전문" in out
    assert "양악수술" in out  # 진료 용어 보존


def test_strong_keeps_medical_noun_after_safe_adjective():
    """'안전한 수술' → '안전한' 만 빼고 '수술' 보존."""
    out = _scrub_ad_phrases("안전한 수술과 안전한 마취", aggressive=True)
    assert "안전한" not in out
    assert "수술" in out and "마취" in out


# ── LIGHT (후기·블로그) — 순수 광고어만, 환자 경험 서술 보존 ──────────
def test_light_removes_only_hype():
    src = "여기 강추! 국내 최고 명품 병원, 효과 만점"
    out = _scrub_ad_phrases(src, aggressive=False)
    for bad in ["강추", "최고", "명품", "효과 만점"]:
        assert bad not in out, f"{bad} 미제거: {out}"


def test_light_keeps_patient_experience():
    """후기의 '완치/안전했/무통/부작용 없' 같은 환자 경험 서술은 LIGHT 에서 보존."""
    src = "수술 후 완치됐고 부작용 없이 안전했어요. 무통 시술이라 편했어요."
    out = _scrub_ad_phrases(src, aggressive=False)
    assert "완치" in out and "부작용" in out and "안전" in out and "무통" in out


def test_light_keeps_topic_keyword():
    out = _scrub_ad_phrases("여드름 흉터 치료 강추", aggressive=False)
    assert "여드름" in out and "흉터" in out and "치료" in out
    assert "강추" not in out


def test_strong_reviewer_additions():
    """medical-language-reviewer 권고: 보장·최첨단·최신장비·유명·완벽·N건성공."""
    src = "효과 보장, 최첨단 장비, 최신 의료기기, 유명한 명원, 완벽한 케어, 1000건 성공"
    out = _scrub_ad_phrases(src, aggressive=True)
    for bad in ["보장", "최첨단", "최신 의료기기", "유명", "완벽"]:
        assert bad not in out, f"{bad} 미제거: {out}"
    assert "성공" not in out or "1000건 성공" not in out


def test_strong_keeps_legit_choesin_context():
    """'최신 논문/최신 연구'는 광고 아님 — 장비·기술 collocation 만 제거(오탐 방지)."""
    out = _scrub_ad_phrases("최신 논문을 참고한 진료, 최신 연구 동향", aggressive=True)
    assert "최신 논문" in out and "최신 연구" in out


def test_light_adds_superiority_keeps_experience():
    """LIGHT 도 최첨단·완벽 등 우월어는 제거하되 환자 경험(완치/안전)은 보존."""
    out = _scrub_ad_phrases("최첨단 장비에 완벽한 시설, 완치됐고 안전했어요", aggressive=False)
    assert "최첨단" not in out and "완벽" not in out
    assert "완치" in out and "안전" in out  # 경험 보존


def test_empty_and_none():
    assert _scrub_ad_phrases("", aggressive=True) == ""
    assert _scrub_ad_phrases("", aggressive=False) == ""
