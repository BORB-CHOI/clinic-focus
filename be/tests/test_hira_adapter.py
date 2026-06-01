"""hira_adapter.map_standard_specialty 단위 테스트.

특히 '여성의원' 폴백 매핑 — '여성'은 진료과 토큰을 모두 검사한 뒤의 맨 마지막
폴백이라, 진료과 토큰이 있으면 그게 우선하고 없을 때만 산부인과로 떨어진다.
(이게 없으면 '에스여성의원' 류가 '기타'로 빠져 제모 등 피부과 추론 쿼리에 오염됨.)
"""

from be.adapters.hira_adapter import map_standard_specialty


def test_women_clinic_falls_back_to_obgyn():
    # 진료과 토큰 없는 '여성의원/여성병원' → 산부인과
    assert map_standard_specialty("의원", "에스여성의원") == "산부인과"
    assert map_standard_specialty("의원", "두번째봄여성의원") == "산부인과"
    assert map_standard_specialty("병원", "호산여성병원") == "산부인과"


def test_specialty_token_wins_over_women():
    # 이름에 진료과 토큰이 있으면 '여성'보다 우선 (여성=맨 마지막 폴백)
    assert map_standard_specialty("의원", "강남여성피부과의원") == "피부과"
    assert map_standard_specialty("의원", "참여성정형외과의원") == "정형외과"


def test_clcd_precedence_over_name():
    # 종별(clCdNm)이 매핑되면 이름 파싱보다 우선 — '여성' 들어가도 치과/한의원
    assert map_standard_specialty("치과의원", "스마일여성치과의원") == "치과"
    assert map_standard_specialty("한의원", "다정여성한의원") == "한의원"


def test_plain_and_unknown():
    assert map_standard_specialty("의원", "리뉴미피부과의원") == "피부과"
    assert map_standard_specialty("의원", "이름없는의원") == "기타"
