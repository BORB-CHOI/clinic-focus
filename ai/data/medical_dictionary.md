# 의료 검색 지식사전 (medical_dictionary)

> 최종 업데이트: 2026-05-29
>
> 검색어 처리 지식사전 — `query_processor`(쿼리 확장)와 `kb_store`(문서-측 동의어 주입)가 소비.
> 일반어 → 한국 병원 본문에 등장하는 학명·전문용어·영문·치료 매핑. 진료과별 섹션 표 한 행 = 1항목.
> 파서·형식 규약: `ai/search/dictionaries.py` docstring. 셀 안 `|` 금지, 동의어는 쉼표 구분.
>
> **의료법 §56**: 평가·광고·효능 표현(잘하는·최고·전문·효과·탁월·완치) 금지. 사실 정보만.
> 검수 이력(2026-05-29): 프로그램 1차 필터(효과·효능·개선·정상화·탁월·최고·1위·명의·
> 베스트·유명·추천 등) + medical-language-reviewer 2차. 화면 노출되는 focus 라벨의
> 효능·심미 암시는 중립화(재생→치료, 심미→미용). 동의어의 표준 시술명(유방축소술·
> 인대강화주사·근력강화운동 등)은 사실 의학용어라 검색 recall 위해 유지(임베딩 전용·미노출).

## 불용어

a, an, are, around, best, good, how, is, near, nearby, the, top, was, were, what, where, which, who, 가, 괜찮은, 괜찮을까, 그거, 그래서, 그런, 그런데, 그리고, 까지, 는, 도, 또는, 를, 만, 베스트, 병원, 부터, 센터, 어느, 어느곳, 어디, 어디가, 어디든, 어디로, 어디서, 어디에, 어떤, 어떤게, 어떤곳, 에게, 에서, 유명, 유명한, 은, 을, 의, 의원, 이, 이거, 이런, 인가요, 일까요, 있나, 있나요, 있는, 있는데, 있어요, 있을까요, 잘봐, 잘하는, 저, 저런, 좋나요, 좋아요, 좋은, 좋을까, 주세요, 추천, 추천 좀, 추천좀, 추천해, 추천해줘, 클리닉, 탑, 하나요, 한테, 할까요, 해주세요, 해줘, 혹은

## 진료과: 피부과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 여드름 | acne, acne vulgaris, 심상성 좌창, 좌창, 면포, comedone, 구진성 여드름, 농포, 결절성 여드름, 아크네 | 여드름·흉터 |
| 여드름 흉터 | acne scar, 위축성 흉터, atrophic scar, 비후성 흉터, hypertrophic scar, 박스카 흉터, ice pick scar, 롤링 흉터, 서브시전, subcision, 프락셔널 레이저 흉터치료 | 여드름·흉터 |
| 기미 | chloasma, melasma, 간반, 색소침착, 갈색반, 후천성 양측성 오타양 반, ABNOM, 토닝, 레이저 토닝 | 색소질환 |
| 잡티 | 색소병변, 주근깨, ephelides, freckle, 흑자, lentigo, 후천성 색소반, 피그먼트 레이저, pigment laser | 색소질환 |
| 주근깨 | ephelides, freckle, 주근깨 색소, 멜라닌 색소, IPL, 아이피엘 | 색소질환 |
| 점 | nevus, 멜라닌 모반, melanocytic nevus, 사마귀양 모반, CO2 레이저, 탄산가스 레이저, 점 제거 | 색소질환 |
| 오타모반 | nevus of Ota, 오타양 모반, 진피 멜라닌 세포증, 태선양 모반, Q-switched Nd:YAG laser, 큐스위치 레이저 | 색소질환 |
| 검버섯 | 지루각화증, seborrheic keratosis, 노인성 색소반, solar lentigo, 일광 흑자, 어븀야그 레이저, Er:YAG laser | 색소질환 |
| 아토피 | 아토피피부염, atopic dermatitis, 아토피성 피부염, 태선화, lichenification, 습진성 병변, 면역조절제 외용 | 염증·알레르기 피부질환 |
| 습진 | eczema, 피부염, dermatitis, 접촉피부염, contact dermatitis, 화폐상 습진, nummular eczema, 한포진, dyshidrotic eczema, 지루피부염, seborrheic dermatitis | 염증·알레르기 피부질환 |
| 두드러기 | urticaria, 담마진, 팽진, wheal, 혈관부종, angioedema, 만성 두드러기, chronic urticaria, 콜린성 두드러기, 항히스타민제 | 염증·알레르기 피부질환 |
| 건선 | psoriasis, 심상성 건선, psoriasis vulgaris, 판상 건선, plaque psoriasis, 인설, scale, Auspitz 징후, 엑시머 레이저, excimer, 광치료, phototherapy | 염증·자가면역 피부질환 |
| 백반증 | vitiligo, 백색반, 멜라닌세포 소실, 탈색소반, depigmentation, 엑시머 레이저, excimer laser, NB-UVB, 협대역 자외선 B | 색소질환 |
| 사마귀 | wart, verruca, 심상성 사마귀, verruca vulgaris, 심상성 우췌, 편평 사마귀, verruca plana, 족저 사마귀, HPV, 인유두종바이러스, 냉동치료, cryotherapy, 냉동요법, 액화질소 | 바이러스성 피부질환 |
| 티눈 | clavus, corn, 경성 티눈, hard corn, 연성 티눈, soft corn, 각질핵, 냉동치료, cryotherapy, CO2 레이저 | 각질질환 |
| 무좀 | 족부백선, tinea pedis, 발백선, 피부사상균증, dermatophytosis, 곰팡이 감염, 항진균제, KOH 검사 | 진균성 피부질환 |
| 손발톱무좀 | 조갑백선, onychomycosis, 조갑진균증, tinea unguium, 손발톱 진균감염, 경구 항진균제, 조갑 레이저 | 진균성 피부질환 |
| 어루러기 | 전풍, tinea versicolor, pityriasis versicolor, 말라세지아, Malassezia, 어루러기 색소변화 | 진균성 피부질환 |
| 대상포진 | herpes zoster, shingles, 수두대상포진바이러스, varicella-zoster virus, VZV, 대상포진후 신경통, postherpetic neuralgia, 항바이러스제 | 바이러스성 피부질환 |
| 단순포진 | herpes simplex, HSV, 단순헤르페스, 입술포진, herpes labialis, 구순포진, 수포성 병변 | 바이러스성 피부질환 |
| 농가진 | impetigo, 수포성 농가진, bullous impetigo, 비수포성 농가진, 황색포도알균, Staphylococcus aureus, 세균성 피부감염 | 세균성 피부질환 |
| 봉와직염 | 연조직염, cellulitis, 피부 연부조직 감염, 단독, erysipelas, 발적, 종창 | 세균성 피부질환 |
| 모낭염 | folliculitis, 모낭 염증, 농포, pustule, 세균성 모낭염, 말라세지아 모낭염 | 염증성 피부질환 |
| 지루성 피부염 | seborrheic dermatitis, 지루피부염, 두피 지루, 비듬, dandruff, 피지선 활성, 항진균 외용 | 염증·알레르기 피부질환 |
| 주사비 | rosacea, 안면홍조, facial flushing, 구진농포성 주사비, papulopustular rosacea, 주사성 피부염, 혈관 레이저, vascular laser | 혈관·홍조질환 |
| 홍조 | facial erythema, 안면홍조, facial flushing, 모세혈관 확장증, telangiectasia, 혈관 레이저, IPL, 585nm 색소혈관 레이저 | 혈관·홍조질환 |
| 한관종 | syringoma, 눈밑 한관종, 에크린 한관종, 양성 부속기 종양, CO2 레이저, 탄산가스 레이저 | 양성 피부종양 |
| 비립종 | milium, milia, 좁쌀 각질낭, 각질 낭종, 눈가 비립종, 면포 압출 | 양성 피부종양 |
| 쥐젖 | 연성 섬유종, acrochordon, skin tag, 피부 쥐젖, 목 쥐젖, CO2 레이저 제거 | 양성 피부종양 |
| 피지낭종 | 표피낭종, epidermal cyst, epidermoid cyst, 분층표피낭, 낭종 절제, 피지선 낭종 | 양성 피부종양 |
| 지방종 | lipoma, 피하 지방종양, 양성 지방종, 지방종 절제 | 양성 피부종양 |
| 피부암 | skin cancer, 기저세포암, basal cell carcinoma, BCC, 편평세포암, squamous cell carcinoma, SCC, 흑색종, melanoma, 피부 조직검사, skin biopsy | 피부종양·검사 |
| 피부 조직검사 | skin biopsy, 펀치 생검, punch biopsy, 절제 생검, excisional biopsy, 조직병리검사, histopathology | 피부종양·검사 |
| 탈모 | alopecia, 남성형 탈모, androgenetic alopecia, M자 탈모, 원형 탈모, alopecia areata, 휴지기 탈모, telogen effluvium, 모발이식, 두피 문신 | 모발·탈모 |
| 원형탈모 | alopecia areata, 원형 탈모증, 자가면역 탈모, 국소 스테로이드 주사, intralesional steroid, 면역요법 | 모발·탈모 |
| 다한증 | hyperhidrosis, 손발 다한증, palmar hyperhidrosis, 액와 다한증, axillary hyperhidrosis, 보툴리눔 톡신, botulinum toxin | 땀·한선질환 |
| 땀띠 | miliaria, 한진, 땀샘 폐쇄, 수정양 땀띠, miliaria crystallina, 홍색 땀띠 | 땀·한선질환 |
| 흉터 | scar, 비후성 흉터, hypertrophic scar, 켈로이드, keloid, 위축성 흉터, atrophic scar, 흉터 레이저, 스테로이드 주사 | 흉터·치료 |
| 켈로이드 | keloid, 비후성 흉터, hypertrophic scar, 켈로이드 흉터, 스테로이드 병변내 주사, intralesional injection | 흉터·치료 |
| 튼살 | striae, 팽창선조, striae distensae, stretch marks, 프락셔널 레이저, fractional laser | 흉터·치료 |
| 주름 | wrinkle, rhytide, 눈가 주름, 팔자주름, nasolabial fold, 보툴리눔 톡신, botulinum toxin, 필러, filler, 고주파 리프팅 | 미용 시술 |
| 모공 | 넓은 모공, enlarged pore, 모공 각화증, keratosis pilaris, 프락셔널 레이저, fractional laser, 피부 재생 레이저 | 미용 시술 |
| 피부미백 | skin whitening, 색소 토닝, 레이저 토닝, laser toning, Q-switched Nd:YAG laser, 미백 관리 | 미용 시술 |
| 피부재생 | skin rejuvenation, 박피, chemical peeling, 화학적 박피, 프락셔널 레이저, fractional laser, 비박피 레이저, non-ablative laser | 미용 시술 |
| 보톡스 | botulinum toxin, 보툴리눔 톡신, botox, 근육 이완 주사, 사각턱 보톡스, 주름 보톡스 | 미용 시술 |
| 필러 | filler, 히알루론산 필러, hyaluronic acid filler, HA filler, 볼륨 필러, 팔자 필러 | 미용 시술 |
| 점 빼기 | nevus removal, 점 제거, CO2 레이저, 탄산가스 레이저, 어븀야그 레이저, Er:YAG laser | 미용 시술 |
| 레이저토닝 | laser toning, 레이저 토닝, Q-switched Nd:YAG laser, 큐스위치 엔디야그, 색소 레이저, 저출력 토닝 | 미용 시술 |
| 아이피엘 | IPL, intense pulsed light, 광치료, 복합 색소 치료, 혈관 색소 IPL | 미용 시술 |
| 피코레이저 | pico laser, picosecond laser, 피코초 레이저, 색소 피코, 문신 제거 피코 | 미용 시술 |
| 문신제거 | tattoo removal, 문신 제거, Q-switched laser, 피코 레이저, picosecond laser, 색소 분해 | 미용 시술 |
| 제모 | hair removal, 레이저 제모, laser hair removal, 알렉산드라이트 레이저, alexandrite laser, 다이오드 레이저, diode laser | 미용 시술 |
| 피부묘기증 | dermographism, dermatographism, 물리적 두드러기, physical urticaria, 긁힘 팽진 | 염증·알레르기 피부질환 |
| 가려움 | 소양증, pruritus, itching, 전신 소양증, 항히스타민제, 피부 건조증 | 증상 |
| 피부건조증 | xerosis, 건성 피부, 건조성 습진, asteatotic eczema, 보습 치료, 피부 장벽 손상 | 증상 |
| 농양 | abscess, 피부 농양, 화농성 병변, 절개 배농, incision and drainage | 세균성 피부질환 |
| 한관각화증 | 모공각화증, keratosis pilaris, 닭살 피부, 모낭 각화, 팔뚝 좁쌀 | 각질질환 |
| 전염성 연속종 | 물사마귀, molluscum contagiosum, 연속종, 큐렛 제거, 바이러스성 결절 | 바이러스성 피부질환 |
| 화상 | burn, 열상 화상, thermal burn, 2도 화상, second-degree burn, 흉터 관리, 피부 재생 치료 | 외상·치료 |
| 동상 | frostbite, 한랭 손상, cold injury, 말단 청색증 | 외상·치료 |
| 화학박피 | chemical peeling, 케미컬 필링, TCA 필링, trichloroacetic acid, 글리콜산 필링, glycolic acid peel, 살리실산 필링 | 미용 시술 |

## 진료과: 성형외과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 쌍꺼풀 수술 | 쌍꺼풀성형, 상안검성형술, blepharoplasty, double eyelid surgery, 매몰법, 절개법, incisional method, double fold | 눈성형 |
| 눈매교정 | 안검하수 교정, 상안검거근 단축술, ptosis correction, 눈매교정술, levator resection, 뮬러근 단축술 | 눈성형 |
| 앞트임 | 내안각췌피 성형, medial epicanthoplasty, epicanthal fold correction, 앞트임 성형 | 눈성형 |
| 뒤트임 | 외안각 성형술, lateral canthoplasty, lateral canthal lengthening, 뒤트임 성형 | 눈성형 |
| 눈밑 지방 | 하안검성형술, lower blepharoplasty, 눈밑 지방 재배치, orbital fat repositioning, 눈밑 다크서클 수술 | 눈성형 |
| 코성형 | 비성형술, rhinoplasty, 융비술, augmentation rhinoplasty, 코 재수술, revision rhinoplasty | 코성형 |
| 매부리코 | 매부리코 교정, hump nose, dorsal hump reduction, 비배부 절골술 | 코성형 |
| 휜코 | 사비 교정, deviated nose, crooked nose, 비중격 만곡증, septal deviation, 비중격 교정술, septoplasty | 코성형 |
| 코끝성형 | 비첨성형술, tip plasty, tip plasty rhinoplasty, 비익연골 성형, alar cartilage | 코성형 |
| 콧볼축소 | 비익축소술, alar reduction, alarplasty, 콧볼 성형 | 코성형 |
| 안면윤곽 | 안면윤곽술, facial contouring, facial bone surgery, 사각턱 수술, 하악각 성형술, mandible angle reduction | 안면골격 |
| 광대축소 | 광대뼈 축소술, zygoma reduction, malar reduction, 협골 축소술 | 안면골격 |
| 턱끝수술 | 턱끝 성형술, genioplasty, mentoplasty, 이부 성형술, 턱끝 절골술 | 안면골격 |
| 양악수술 | 양악 수술, orthognathic surgery, two-jaw surgery, 상하악 골절술, 악교정수술, Le Fort I osteotomy, BSSO | 안면골격 |
| 주걱턱 | 하악전돌증, mandibular prognathism, prognathism, 하악 후퇴술 | 안면골격 |
| 무턱 | 소턱증, micrognathia, retrognathia, 턱끝 전진술, chin augmentation | 안면골격 |
| 가슴성형 | 유방확대술, breast augmentation, augmentation mammoplasty, 보형물 삽입술, breast implant, 유방 보형물 | 유방성형 |
| 가슴축소 | 유방축소술, reduction mammoplasty, breast reduction, 거대유방증, macromastia | 유방성형 |
| 가슴처짐 | 유방하수, breast ptosis, mastoptosis, 유방고정술, mastopexy, 가슴 거상술 | 유방성형 |
| 유방재건 | 유방재건술, breast reconstruction, 자가조직 유방재건, DIEP flap, 유두 재건술, nipple reconstruction | 재건성형 |
| 여유증 | 여성형유방, gynecomastia, 남성 유방축소술, 여유증 수술 | 유방성형 |
| 함몰유두 | 함몰유두 교정, inverted nipple, nipple inversion correction, 유두 성형술 | 유방성형 |
| 지방흡입 | 지방흡입술, liposuction, lipoplasty, suction-assisted lipectomy, 복부 지방흡입, tumescent liposuction | 체형성형 |
| 지방이식 | 자가지방이식, fat graft, fat grafting, autologous fat transfer, fat transfer, 미세지방이식 | 체형성형 |
| 복부성형 | 복벽성형술, abdominoplasty, tummy tuck, 복부 처짐 교정, 복직근 봉합 | 체형성형 |
| 안면거상 | 안면거상술, face lift, rhytidectomy, 주름 제거술, SMAS 거상술, 목거상술, neck lift | 항노화 |
| 이마거상 | 이마거상술, forehead lift, brow lift, 내시경 이마거상, 눈썹 거상술 | 항노화 |
| 실리프팅 | 실 리프팅, thread lift, 매선 리프팅, 녹는실 리프팅, PDO thread | 항노화 |
| 보톡스 | 보툴리눔 톡신, botulinum toxin, botox, 사각턱 보톡스, 주름 보톡스, botulinum toxin type A | 미용주사 |
| 필러 | 피부 충전제, filler, dermal filler, 히알루론산 필러, hyaluronic acid filler, HA filler, 팔자주름 필러 | 미용주사 |
| 흉터제거 | 흉터성형술, scar revision, 흉터 교정술, 비후성 반흔, hypertrophic scar, 흉터 재수술 | 재건성형 |
| 켈로이드 | 켈로이드 흉터, keloid, 켈로이드 절제술, 흉터 주사, 스테로이드 주사 | 재건성형 |
| 화상 | 화상 치료, burn, burn injury, 화상 재건술, 피부이식술, skin graft, burn reconstruction | 재건성형 |
| 피부이식 | 피부이식술, skin graft, skin grafting, STSG, split-thickness skin graft, 전층 피부이식 | 재건성형 |
| 수부외과 | 손 수술, hand surgery, 수지접합술, replantation, 건 봉합술, tendon repair, 수근관 증후군, carpal tunnel | 수부·재건 |
| 수지접합 | 수지접합술, digit replantation, finger replantation, 절단 손가락 접합, 미세수술, microsurgery | 수부·재건 |
| 피판술 | 유리피판술, free flap, 피판 이식, flap surgery, 미세혈관 문합술, microvascular anastomosis | 재건성형 |
| 구순구개열 | 입술갈림증, cleft lip, cleft palate, 순열, 구개열, 구순열 교정술, 입술갈림증 수술 | 두개안면 |
| 두개안면기형 | 두개안면성형, craniofacial surgery, craniosynostosis, 두개골 조기유합증, 안면기형 교정 | 두개안면 |
| 안면마비 | 안면신경마비, facial palsy, facial paralysis, 안면신경 재건, facial reanimation, 신경 이식술 | 재건성형 |
| 다한증 | 국소 다한증, hyperhidrosis, 겨드랑이 다한증, axillary hyperhidrosis, 교감신경 절제술, ETS | 기타 |
| 눈썹문신 제거 | 문신 제거, tattoo removal, 레이저 문신 제거, laser tattoo removal, 피코 레이저 | 레이저 |
| 점 제거 | 모반 제거, nevus removal, mole removal, 레이저 점빼기, CO2 레이저, 흑색종 감별 | 레이저 |
| 귀성형 | 귀 재건술, otoplasty, auricular reconstruction, 돌출귓바퀴 교정, prominent ear, 소이증, microtia | 재건성형 |
| 입술성형 | 입술 축소술, 입술 확대술, lip reduction, lip augmentation, 구순 성형술 | 안면성형 |
| 이마성형 | 이마 지방이식, 이마 보형물, forehead augmentation, 이마 필러 | 안면성형 |
| 피부암 | 피부 종양, skin cancer, 기저세포암, basal cell carcinoma, 편평세포암, squamous cell carcinoma, 악성흑색종, melanoma, 종양 절제술 | 재건성형 |
| 림프부종 | 림프부종 수술, lymphedema, 림프관-정맥 문합술, LVA, lymphaticovenous anastomosis | 미세수술 |
| 욕창 | 욕창 재건술, pressure sore, pressure ulcer, decubitus ulcer, 피판 재건 | 재건성형 |
| 비절개 눈성형 | 매몰법 쌍꺼풀, non-incisional blepharoplasty, buried suture technique, 무절개 쌍꺼풀 | 눈성형 |
| 안면비대칭 | 안면 비대칭 교정, facial asymmetry, 안면골 비대칭, 비대칭 교정술 | 안면골격 |

## 진료과: 정형외과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 허리 디스크 | 요추 추간판 탈출증, 추간판 탈출증, HIVD, herniated intervertebral disc, lumbar disc herniation, 수핵 탈출, 신경근 압박 | 척추 |
| 목 디스크 | 경추 추간판 탈출증, cervical disc herniation, 경추 HIVD, 신경근병증, radiculopathy, 방사통 | 척추 |
| 척추관 협착증 | 요추관 협착증, lumbar spinal stenosis, spinal stenosis, 신경관 협착, 마미증후군, cauda equina | 척추 |
| 좌골신경통 | sciatica, 하지 방사통, 신경근 압박, 이상근 증후군, piriformis syndrome | 척추 |
| 척추 측만증 | scoliosis, 특발성 측만증, 콥스각, Cobb angle, 척추 변형 | 척추 |
| 척추 전방전위증 | 전방전위증, spondylolisthesis, 척추 분리증, spondylolysis, 협부 결손 | 척추 |
| 압박 골절 | 척추 압박 골절, compression fracture, vertebral compression fracture, 골다공증성 골절, 척추체 골절, 척추체 성형술, vertebroplasty, kyphoplasty | 척추 |
| 거북목 | 일자목, 거북목 증후군, forward head posture, 경추 후만, text neck, 경추 정렬 이상 | 척추 |
| 무릎 통증 | 슬관절 통증, knee pain, 슬관절, knee joint, 관절통, arthralgia | 관절 |
| 퇴행성 관절염 | 골관절염, osteoarthritis, degenerative arthritis, 연골 마모, 관절 연골, cartilage | 관절 |
| 류마티스 관절염 | rheumatoid arthritis, 활막염, synovitis, 자가면역 관절염 | 관절 |
| 십자인대 파열 | 전방십자인대 파열, anterior cruciate ligament, ACL, 후방십자인대, posterior cruciate ligament, PCL, 인대 재건술, ligament reconstruction | 스포츠 손상 |
| 반월상연골 파열 | 반월판 파열, meniscus tear, meniscal tear, 반월상 연골 손상, 연골판 봉합술, meniscectomy, 연골판 절제술 | 스포츠 손상 |
| 연골 연화증 | 슬개골 연골연화증, chondromalacia, chondromalacia patellae, 연골 손상, cartilage defect | 관절 |
| 인공관절 | 인공관절 치환술, 관절 치환술, arthroplasty, joint replacement, 인공 슬관절 치환술, total knee replacement, TKR, 인공 고관절 치환술, total hip replacement, THR | 관절 |
| 관절경 | 관절경 수술, arthroscopy, arthroscopic surgery, 관절 내시경, 최소 침습 수술 | 관절 |
| 오십견 | 유착성 관절낭염, adhesive capsulitis, 동결견, frozen shoulder, 견관절 구축, 관절낭 유착 | 어깨 |
| 회전근개 파열 | rotator cuff tear, rotator cuff, 극상근 파열, supraspinatus, 회전근개 봉합술, cuff repair | 어깨 |
| 어깨 충돌 증후군 | 견봉하 충돌 증후군, shoulder impingement syndrome, impingement, 견봉 성형술, acromioplasty | 어깨 |
| 석회성 건염 | 석회화 건염, calcific tendinitis, 석회 침착, calcific tendinopathy, 체외충격파, ESWT | 어깨 |
| 어깨 탈구 | 견관절 탈구, shoulder dislocation, 재발성 탈구, 관절와순 파열, labral tear, Bankart lesion, 방카르트 병변 | 어깨 |
| 테니스 엘보 | 외측 상과염, lateral epicondylitis, tennis elbow, 주관절 외상과염, 신전건 손상 | 팔꿈치 |
| 골프 엘보 | 내측 상과염, medial epicondylitis, golfer's elbow, 주관절 내상과염, 굴곡건 손상 | 팔꿈치 |
| 손목터널증후군 | 수근관 증후군, carpal tunnel syndrome, 정중신경 압박, median nerve, 수근관 감압술, carpal tunnel release | 수부 |
| 방아쇠 수지 | 방아쇠 손가락, trigger finger, 협착성 건초염, stenosing tenosynovitis, 굴곡건 협착 | 수부 |
| 손목 건초염 | 드퀘르벵 건초염, de Quervain tenosynovitis, 건초염, tenosynovitis, 손목 건염, wrist tendinitis | 수부 |
| 결절종 | 손목 결절종, ganglion cyst, 건초 낭종, 물혹 | 수부 |
| 발목 염좌 | 족관절 염좌, ankle sprain, 인대 손상, ligament sprain, 외측 인대 손상, ATFL, 전거비인대 | 족부 |
| 족저근막염 | 족저 근막염, plantar fasciitis, 발바닥 통증, heel pain, 종골 골극, heel spur, 체외충격파, ESWT | 족부 |
| 무지외반증 | 무지 외반증, hallux valgus, bunion, 엄지발가락 변형, 교정 절골술, osteotomy | 족부 |
| 아킬레스건 파열 | Achilles tendon rupture, 아킬레스건염, Achilles tendinitis, 건 봉합술, tendon repair | 족부 |
| 고관절 통증 | 고관절, hip joint, 고관절염, hip pain, 대퇴비구 충돌, femoroacetabular impingement, FAI | 고관절 |
| 대퇴골두 무혈성 괴사 | avascular necrosis, AVN, osteonecrosis, 골괴사, 대퇴골두 괴사 | 고관절 |
| 골절 | fracture, 개방성 골절, open fracture, 폐쇄성 골절, 분쇄 골절, comminuted fracture, 관혈적 정복술, open reduction, 내고정, internal fixation, ORIF | 외상 |
| 탈구 | 관절 탈구, dislocation, 아탈구, subluxation, 도수 정복, closed reduction | 외상 |
| 골다공증 | osteoporosis, 골밀도 감소, bone mineral density, BMD, 골다공증성 골절, 골밀도 검사, DEXA | 골대사 |
| 통풍 | gout, 통풍성 관절염, gouty arthritis, 요산 결정, uric acid, 결정 유발성 관절염 | 관절 |
| 베이커 낭종 | 슬와부 낭종, Baker cyst, popliteal cyst, 오금 물혹 | 관절 |
| 점액낭염 | 활액낭염, bursitis, 주두 점액낭염, olecranon bursitis, 전자부 점액낭염 | 관절 |
| 성장통 | growing pains, 오스굿씨병, Osgood-Schlatter disease, 경골 조면 골단염, 소아 정형 | 소아 정형 |
| 사경 | torticollis, 선천성 근성 사경, congenital muscular torticollis, 흉쇄유돌근 | 소아 정형 |
| 평발 | 편평족, flatfoot, pes planus, 발 아치 소실, 후족부 외반 | 족부 |
| 다리 저림 | 하지 저림, leg numbness, 감각 이상, paresthesia, 방사통, radiating pain, 신경 압박 | 척추 |
| 근막통증 증후군 | 근막동통 증후군, myofascial pain syndrome, 통증 유발점, trigger point, 근육통, 근육 결림 | 재활 |
| X-ray 검사 | 단순 방사선 촬영, X-ray, radiography, 엑스레이, 골 사진 | 검사 |
| MRI 검사 | 자기공명영상, MRI, magnetic resonance imaging, 연부조직 검사, 인대 검사 | 검사 |
| 초음파 검사 | 근골격계 초음파, ultrasound, ultrasonography, 초음파 유도 주사, ultrasound-guided injection | 검사 |
| 체외충격파 치료 | 체외충격파, ESWT, extracorporeal shock wave therapy, 충격파 치료 | 비수술 치료 |
| 도수치료 | 도수 치료, manual therapy, manipulation, 관절 가동술, mobilization, 물리치료, physical therapy | 재활 |
| 프롤로 주사 | 프롤로테라피, prolotherapy, 증식치료, 인대 증식 주사 | 비수술 치료 |
| 신경차단술 | 신경 차단술, nerve block, 경막외 주사, epidural injection, 선택적 신경근 차단술, 통증 주사 | 비수술 치료 |
| 관절 주사 | 관절강 주사, intra-articular injection, 히알루론산 주사, hyaluronic acid, 연골 주사, 스테로이드 주사 | 비수술 치료 |
| 골절 깁스 | 석고 고정, cast, casting, 부목, splint, 외고정, external fixation | 외상 |
| 강직성 척추염 | ankylosing spondylitis, AS, 천장관절염, sacroiliitis, 척추 강직 | 척추 |
| 회전근개 건염 | 견관절 건염, rotator cuff tendinitis, 극상근 건염, supraspinatus tendinitis, 어깨 힘줄염 | 어깨 |
| 추간판 변성 | 디스크 변성, disc degeneration, 퇴행성 디스크, degenerative disc disease, 추간판 팽윤, disc bulging | 척추 |

## 진료과: 신경외과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 허리 디스크 | 요추 추간판 탈출증, lumbar disc herniation, HLD, herniated lumbar disc, 요추간판수핵탈출증, disc herniation | 척추 |
| 목 디스크 | 경추 추간판 탈출증, cervical disc herniation, HCD, 경추간판수핵탈출증, cervical disc | 척추 |
| 척추관 협착증 | 요추 척추관 협착증, spinal stenosis, lumbar spinal stenosis, 경추 척추관 협착증, central canal stenosis, neurogenic claudication | 척추 |
| 척추 측만증 | scoliosis, 척추옆굽음증, idiopathic scoliosis, spinal deformity | 척추 |
| 척추 전방전위증 | spondylolisthesis, 척추 미끄럼증, 요추 전방전위증, isthmic spondylolisthesis | 척추 |
| 척추압박골절 | vertebral compression fracture, VCF, 골다공증성 압박골절, osteoporotic compression fracture, 추체 골절 | 척추 |
| 좌골신경통 | sciatica, 좌골 신경통, 방사통, radiculopathy, 신경근병증, radicular pain | 척추 |
| 척추 후종인대 골화증 | ossification of posterior longitudinal ligament, OPLL, 후종인대골화증 | 척추 |
| 척수종양 | spinal tumor, spinal cord tumor, 척수강내 종양, intramedullary tumor, extramedullary tumor | 척추 |
| 퇴행성 척추질환 | degenerative spine disease, 척추증, spondylosis, 퇴행성 디스크, degenerative disc disease | 척추 |
| 뇌졸중 | stroke, cerebrovascular accident, CVA, 뇌혈관질환, 뇌경색, cerebral infarction, 뇌출혈, cerebral hemorrhage | 뇌혈관 |
| 뇌출혈 | cerebral hemorrhage, intracerebral hemorrhage, ICH, 뇌내출혈, 지주막하출혈, subarachnoid hemorrhage, SAH, 경막하출혈, subdural hemorrhage | 뇌혈관 |
| 뇌동맥류 | cerebral aneurysm, intracranial aneurysm, 뇌혈관 꽈리, unruptured aneurysm, 파열성 동맥류 | 뇌혈관 |
| 뇌경색 | cerebral infarction, ischemic stroke, 뇌허혈, cerebral ischemia | 뇌혈관 |
| 뇌혈관 기형 | arteriovenous malformation, AVM, 동정맥기형, cavernous malformation, 해면상 혈관종 | 뇌혈관 |
| 모야모야병 | moyamoya disease, 모야모야, moyamoya | 뇌혈관 |
| 경동맥 협착 | carotid artery stenosis, carotid stenosis, 경동맥 협착증, carotid stenting | 뇌혈관 |
| 뇌종양 | brain tumor, intracranial tumor, 뇌신생물, brain neoplasm | 뇌종양 |
| 수막종 | meningioma, 뇌수막종, 경막 종양 | 뇌종양 |
| 교모세포종 | glioblastoma, glioblastoma multiforme, GBM, 악성 신경교종, malignant glioma, glioma, 신경교종 | 뇌종양 |
| 뇌하수체 종양 | pituitary tumor, pituitary adenoma, 뇌하수체 선종, 경접형동 접근법, transsphenoidal approach | 뇌종양 |
| 청신경 종양 | acoustic neuroma, vestibular schwannoma, 전정신경초종, 청신경초종, schwannoma | 뇌종양 |
| 전이성 뇌종양 | metastatic brain tumor, brain metastasis, 뇌전이, metastatic tumor | 뇌종양 |
| 삼차신경통 | trigeminal neuralgia, TN, 삼차 신경병증, 안면 통증, facial pain, microvascular decompression, 미세혈관 감압술 | 기능신경 |
| 안면경련 | hemifacial spasm, HFS, 반측 안면경련, 안면신경 경련 | 기능신경 |
| 파킨슨병 | Parkinson's disease, PD, 파킨슨, deep brain stimulation, DBS, 뇌심부자극술 | 기능신경 |
| 수전증 | essential tremor, 본태성 진전, tremor, 진전, 손떨림 | 기능신경 |
| 뇌전증 | epilepsy, 간질, seizure, 발작, epilepsy surgery, 간질 수술 | 기능신경 |
| 손목터널증후군 | carpal tunnel syndrome, CTS, 수근관 증후군, 정중신경 압박, median nerve compression | 말초신경 |
| 팔꿈치터널증후군 | cubital tunnel syndrome, 주관 증후군, ulnar nerve entrapment, 척골신경 포착 | 말초신경 |
| 말초신경 손상 | peripheral nerve injury, 신경 압박, nerve entrapment, 신경 포착 증후군, entrapment neuropathy | 말초신경 |
| 수두증 | hydrocephalus, 정상압 수두증, normal pressure hydrocephalus, NPH, 뇌실복강 단락술, ventriculoperitoneal shunt, VP shunt | 기타 |
| 머리 외상 | head trauma, traumatic brain injury, TBI, 외상성 뇌손상, 두부 손상, 뇌진탕, concussion | 외상 |
| 경막하 혈종 | subdural hematoma, SDH, 만성 경막하 혈종, chronic subdural hematoma, 경막외 혈종, epidural hematoma, EDH | 외상 |
| 두개골 골절 | skull fracture, 두개 골절, 함몰 골절, depressed fracture | 외상 |
| 척수 손상 | spinal cord injury, SCI, 척수손상, 사지마비, quadriplegia, 하지마비, paraplegia | 외상 |
| 디스크 시술 | nucleoplasty, 신경성형술, 경막외 신경성형술, epidural neuroplasty, 고주파 수핵감압술, percutaneous disc decompression, 신경차단술, nerve block | 척추 |
| 디스크 수술 | discectomy, microdiscectomy, 미세현미경 디스크 절제술, 추간판 절제술, 내시경 디스크 수술, endoscopic discectomy | 척추 |
| 척추 유합술 | spinal fusion, 척추 고정술, 요추 유합술, lumbar interbody fusion, TLIF, PLIF, 척추 나사 고정 | 척추 |
| 척추 감압술 | laminectomy, 후궁 절제술, decompression, laminotomy, 후궁 성형술 | 척추 |
| 척추 풍선 시술 | vertebroplasty, 척추 성형술, kyphoplasty, 골시멘트 주입술, balloon kyphoplasty | 척추 |
| 감마나이프 | gamma knife, 감마나이프 수술, stereotactic radiosurgery, SRS, 정위 방사선 수술, cyberknife | 뇌종양 |
| 뇌동맥류 코일색전술 | coil embolization, 코일 색전술, endovascular coiling, 뇌동맥류 결찰술, aneurysm clipping, clipping | 뇌혈관 |
| 뇌 MRI | brain MRI, 자기공명영상, 뇌 자기공명영상, MRI | 검사 |
| 뇌 CT | brain CT, computed tomography, 전산화 단층촬영, 뇌 단층촬영 | 검사 |
| 뇌혈관 조영술 | cerebral angiography, 뇌혈관 촬영, CT angiography, CTA, MR angiography, MRA | 검사 |
| 근전도 검사 | electromyography, EMG, 신경전도검사, nerve conduction study, NCS | 검사 |
| 척수 조영술 | myelography, 척수강 조영술, myelogram | 검사 |
| 골밀도 검사 | bone densitometry, DEXA, 골다공증 검사, bone mineral density, BMD | 검사 |
| 목 통증 | cervical pain, 경부 통증, neck pain, 경추통 | 척추 |
| 허리 통증 | low back pain, 요통, LBP, lumbago | 척추 |
| 두통 | headache, cephalalgia, 만성 두통, chronic headache | 뇌 |
| 어지럼증 | dizziness, vertigo, 현훈, 어지러움 | 뇌 |
| 손발 저림 | numbness, 사지 저림, paresthesia, 감각이상, tingling | 말초신경 |
| 안면마비 | facial palsy, facial paralysis, 안면신경 마비, facial nerve palsy | 말초신경 |

## 진료과: 재활의학과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 허리 디스크 | 요추 추간판 탈출증, 椎間板脱出症, lumbar disc herniation, HIVD, herniated intervertebral disc, 요추간판 헤르니아, 디스크 탈출 | 척추재활 |
| 목 디스크 | 경추 추간판 탈출증, cervical disc herniation, cervical HIVD, 경추간판 탈출, 경추 추간판 | 척추재활 |
| 척추관 협착증 | 요추 척추관 협착증, spinal stenosis, lumbar spinal stenosis, 척주관 협착, 신경관 협착 | 척추재활 |
| 척추측만증 | 측만증, scoliosis, 특발성 척추측만증, idiopathic scoliosis, 척추 변형 | 척추재활 |
| 거북목 | 일자목, 거북목 증후군, forward head posture, text neck, 경추 전만 소실, turtle neck syndrome | 척추재활 |
| 척추전방전위증 | 전방전위증, spondylolisthesis, 척추 분리증, spondylolysis, 척추 미끄러짐 | 척추재활 |
| 오십견 | 동결견, 유착성 관절낭염, adhesive capsulitis, frozen shoulder, 견관절 유착, 어깨 관절낭염 | 근골격재활 |
| 회전근개 파열 | 회전근개 증후군, rotator cuff syndrome, rotator cuff tear, 극상근 건염, supraspinatus tendinopathy, 회전근개 손상 | 근골격재활 |
| 테니스 엘보 | 외측 상과염, lateral epicondylitis, tennis elbow, 주관절 외상과염, 상완골 외측상과염 | 근골격재활 |
| 골프 엘보 | 내측 상과염, medial epicondylitis, golfer's elbow, 주관절 내상과염 | 근골격재활 |
| 손목터널증후군 | 수근관 증후군, carpal tunnel syndrome, CTS, 정중신경 압박, median nerve entrapment, 손목 수근관 | 신경근육질환 |
| 방아쇠 수지 | 방아쇠 손가락, trigger finger, 협착성 건초염, stenosing tenosynovitis | 근골격재활 |
| 무릎 통증 | 슬관절 통증, knee pain, 무릎 관절염, 슬개대퇴 통증증후군, patellofemoral pain syndrome, 슬관절 골관절염 | 근골격재활 |
| 십자인대 파열 | 전방십자인대 파열, ACL tear, anterior cruciate ligament injury, 후방십자인대 손상, PCL injury, 무릎인대 손상 | 근골격재활 |
| 반월상연골 손상 | 반월판 파열, meniscus tear, meniscal injury, 연골판 손상, 반달연골 파열 | 근골격재활 |
| 발목 염좌 | 발목 삠, ankle sprain, 족관절 염좌, 인대 손상, 발목 인대 파열 | 근골격재활 |
| 족저근막염 | 발바닥 통증, plantar fasciitis, 족저 근막염, 발뒤꿈치 통증, heel pain, 종골 골극 | 근골격재활 |
| 아킬레스건염 | 아킬레스 건병증, achilles tendinopathy, achilles tendinitis, 종골건 건염, 아킬레스건 손상 | 근골격재활 |
| 퇴행성 관절염 | 골관절염, osteoarthritis, OA, 퇴행성 골관절염, 관절 연골 마모, degenerative arthritis | 근골격재활 |
| 근막통증증후군 | 근막동통증후군, myofascial pain syndrome, MPS, 근막통증, 트리거 포인트, trigger point | 통증재활 |
| 섬유근육통 | 섬유근통, fibromyalgia, FMS, 광범위 근육통, 전신 통증증후군 | 통증재활 |
| 좌골신경통 | 좌골 신경통, sciatica, sciatic neuralgia, 하지 방사통, radiating leg pain, 좌골신경 압박 | 통증재활 |
| 신경병증성 통증 | 신경병성 통증, neuropathic pain, 말초신경병증, peripheral neuropathy, 신경통, neuralgia | 통증재활 |
| 대상포진 후 신경통 | 포진후 신경통, postherpetic neuralgia, PHN, 대상포진 후유증, 신경통 | 통증재활 |
| 복합부위통증증후군 | 복합부위 통증증후군, complex regional pain syndrome, CRPS, 반사성 교감신경 이영양증, RSD | 통증재활 |
| 뇌졸중 재활 | 중풍 재활, stroke rehabilitation, 뇌경색 재활, 뇌출혈 재활, cerebrovascular accident, CVA | 신경재활 |
| 편마비 | 반신마비, hemiplegia, hemiparesis, 편측 마비, 한쪽 마비 | 신경재활 |
| 연하장애 | 삼킴장애, dysphagia, swallowing disorder, 삼킴 곤란, 연하 곤란, 흡인 | 신경재활 |
| 보행장애 | 걸음 이상, gait disturbance, gait disorder, 편마비 보행, hemiplegic gait, 보행 이상 | 신경재활 |
| 척수손상 | 척수 손상, spinal cord injury, SCI, 사지마비, tetraplegia, 하지마비, paraplegia | 신경재활 |
| 외상성 뇌손상 | 뇌손상, traumatic brain injury, TBI, 뇌외상, 후천성 뇌손상, acquired brain injury | 신경재활 |
| 경직 | 근경직, spasticity, 근육 강직, muscle stiffness, 경직성 마비 | 신경재활 |
| 파킨슨병 재활 | 파킨슨 재활, Parkinson's disease rehabilitation, 파킨슨증, parkinsonism, 운동장애 재활 | 신경재활 |
| 말초신경병증 | 말초 신경병증, peripheral neuropathy, 당뇨병성 신경병증, diabetic neuropathy, 다발신경병증, polyneuropathy | 신경근육질환 |
| 안면마비 | 얼굴마비, facial palsy, facial nerve palsy, 벨마비, Bell's palsy, 구안와사 | 신경근육질환 |
| 척추압박골절 | 압박골절, compression fracture, vertebral compression fracture, 골다공증성 골절, 척추체 골절 | 척추재활 |
| 골다공증 | 뼈엉성증, osteoporosis, 골밀도 감소, bone mineral density, 골감소증, osteopenia | 근골격재활 |
| 림프부종 | 림프 부종, lymphedema, 상지 림프부종, 유방암 후 림프부종, 림프 순환 장애 | 암재활 |
| 뇌성마비 | 뇌성 마비, cerebral palsy, CP, 경직형 뇌성마비, 소아 뇌성마비 | 소아재활 |
| 발달지연 | 발달 지연, developmental delay, global developmental delay, 운동발달 지연, 언어발달 지연 | 소아재활 |
| 사경 | 기운목, torticollis, 사경증, 근성 사경, congenital muscular torticollis, 선천성 근성 사경 | 소아재활 |
| 평발 | 편평족, flatfoot, pes planus, 평발증, 족부 변형 | 소아재활 |
| 근육통 | 근육 통증, myalgia, 근육 결림, 근긴장, muscle tension | 통증재활 |
| 건염 | 힘줄염, tendinitis, tendinopathy, 건병증, 건초염, tenosynovitis | 근골격재활 |
| 석회성 건염 | 석회화 건염, calcific tendinitis, calcifying tendinopathy, 어깨 석회화, 견관절 석회 | 근골격재활 |
| 근전도 검사 | 근전도, electromyography, EMG, 신경전도검사, nerve conduction study, NCS, 침근전도 | 전기진단검사 |
| 신경전도검사 | 신경전도 속도검사, nerve conduction study, NCS, nerve conduction velocity, 말초신경 검사 | 전기진단검사 |
| 보행분석 | 보행 분석, gait analysis, gait lab, 3차원 보행분석, 운동형상학 분석, kinematic analysis | 진단평가 |
| 근골격 초음파 | 관절 초음파, musculoskeletal ultrasound, MSK ultrasound, 초음파 검사, 연부조직 초음파 | 진단평가 |
| 도수치료 | 도수 치료, manual therapy, manipulative therapy, 수기치료, 관절가동술, joint mobilization, 연부조직 도수치료 | 물리치료 |
| 체외충격파 | 체외충격파 치료, extracorporeal shock wave therapy, ESWT, 충격파 치료, 집속형 충격파, focused shock wave | 물리치료 |
| 물리치료 | 물리 치료, physical therapy, PT, physiotherapy, 전기치료, 온열치료, 치료적 운동, therapeutic exercise | 물리치료 |
| 작업치료 | 작업 치료, occupational therapy, OT, 일상생활동작 훈련, ADL training, 상지 작업치료 | 신경재활 |
| 운동치료 | 운동 치료, therapeutic exercise, 근력강화 운동, stretching, 스트레칭, 코어 운동, 근력 운동 | 물리치료 |
| 견인치료 | 견인 치료, traction therapy, spinal traction, 척추 견인, 경추 견인, 요추 견인 | 물리치료 |
| 전기자극치료 | 전기자극 치료, electrical stimulation therapy, TENS, 경피적 전기신경자극, functional electrical stimulation, FES, 간섭파 치료 | 물리치료 |
| 프롤로치료 | 프롤로 치료, prolotherapy, 증식치료, regenerative injection, 인대증식치료 | 통증재활 |
| 트리거포인트 주사 | 통증유발점 주사, trigger point injection, TPI, 압통점 주사, 근막 주사 | 통증재활 |
| 연하재활 | 삼킴 재활, swallowing rehabilitation, 연하 재활치료, 연하장애 치료, 비디오 투시 연하검사, VFSS | 신경재활 |
| 인지재활 | 인지 재활, cognitive rehabilitation, 인지치료, 기억력 훈련, 집중력 훈련 | 신경재활 |
| 언어치료 | 언어 치료, speech therapy, speech-language therapy, 실어증 치료, 조음치료, 구음장애 | 신경재활 |
| 보조기 | 보조기 처방, orthosis, brace, 보조기구, 족하수 보조기, AFO, ankle foot orthosis | 재활보조 |
| 의지 | 의수, 의족, prosthesis, artificial limb, 절단지 재활, amputation rehabilitation | 재활보조 |
| 이상근증후군 | 이상근 증후군, piriformis syndrome, 둔부 통증, 좌골신경 압박 | 통증재활 |
| 척추측만 도수 | 측만증 교정운동, schroth method, 슈로스 운동, 측만증 재활운동 | 척추재활 |
| 경추성 두통 | 경추 기인성 두통, cervicogenic headache, 목 기인 두통, 경부 두통 | 통증재활 |
| 턱관절 장애 | 악관절 장애, temporomandibular joint disorder, TMD, TMJ disorder, 턱관절 통증 | 근골격재활 |
| 근감소증 | 근육감소증, sarcopenia, 노인성 근감소, 근육량 감소 | 노인재활 |
| 낙상 | 낙상 위험, fall risk, 균형장애, balance disorder, 낙상 예방 | 노인재활 |
| 심장재활 | 심장 재활, cardiac rehabilitation, 심폐재활, cardiopulmonary rehabilitation, 운동부하검사 | 심폐재활 |
| 호흡재활 | 호흡 재활, pulmonary rehabilitation, 폐재활, 호흡근 훈련, respiratory muscle training | 심폐재활 |
| 배뇨장애 재활 | 신경인성 방광, neurogenic bladder, 배뇨 재활, 방광 재활 | 신경재활 |

## 진료과: 마취통증의학과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 허리 디스크 | 요추 추간판 탈출증, 추간판탈출증, herniated intervertebral disc, HIVD, lumbar disc herniation, 수핵탈출증, nucleus pulposus | 척추 통증 |
| 목 디스크 | 경추 추간판 탈출증, cervical disc herniation, 경추간판탈출증, cervical HIVD | 척추 통증 |
| 척추관 협착증 | 요추관협착증, spinal stenosis, lumbar spinal stenosis, 신경공 협착, 척추협착 | 척추 통증 |
| 허리 통증 | 요통, low back pain, LBP, 요추부 통증, 만성 요통, chronic low back pain | 척추 통증 |
| 목 통증 | 경부통, neck pain, cervicalgia, 경추부 통증 | 척추 통증 |
| 좌골신경통 | sciatica, 좌골신경 압박, 방사통, radiating pain, 하지 방사통 | 척추 통증 |
| 대상포진 | herpes zoster, varicella-zoster virus, VZV, 대상포진 후 신경통, postherpetic neuralgia, PHN, postzoster neuralgia | 신경병증성 통증 |
| 삼차신경통 | trigeminal neuralgia, TN, trigeminal nerve, 삼차신경 통증 | 신경병증성 통증 |
| 복합부위통증증후군 | CRPS, complex regional pain syndrome, 반사성 교감신경 위축증, reflex sympathetic dystrophy, RSD, causalgia, 작열통 | 신경병증성 통증 |
| 섬유근육통 | fibromyalgia, fibromyalgia syndrome, FMS, 전신 근육통 | 만성 통증 |
| 근막통증증후군 | 근막동통증후군, myofascial pain syndrome, MPS, trigger point, 통증유발점 | 근골격 통증 |
| 오십견 | 유착성 관절낭염, 동결견, frozen shoulder, adhesive capsulitis, 견관절 유착 | 근골격 통증 |
| 어깨 통증 | 견관절 통증, shoulder pain, 회전근개 통증, rotator cuff | 근골격 통증 |
| 무릎 통증 | 슬관절 통증, knee pain, 퇴행성 관절염, osteoarthritis, 골관절염, 슬관절염 | 근골격 통증 |
| 테니스 엘보 | 외측 상과염, lateral epicondylitis, tennis elbow, 팔꿈치 통증 | 근골격 통증 |
| 골프 엘보 | 내측 상과염, medial epicondylitis, golfer's elbow | 근골격 통증 |
| 족저근막염 | plantar fasciitis, 발바닥 통증, 발뒤꿈치 통증, heel pain | 근골격 통증 |
| 손목 터널 증후군 | 수근관 증후군, carpal tunnel syndrome, CTS, 정중신경 압박, median nerve | 신경병증성 통증 |
| 두통 | headache, 긴장성 두통, tension headache, 편두통, migraine, 군발두통, cluster headache | 두통·안면통증 |
| 꼬리뼈 통증 | 미골통, coccygodynia, coccydynia | 척추 통증 |
| 신경차단술 | nerve block, 경막외 신경차단술, epidural block, epidural steroid injection, ESI, 선택적 신경근 차단술, selective nerve root block, SNRB, 경추간공 차단, transforaminal block, 후궁간 차단, interlaminar block | 중재적 통증치료 |
| 꼬리뼈 주사 | 미추차단, caudal block, caudal epidural injection, 꼬리뼈 경막외 주사 | 중재적 통증치료 |
| 신경성형술 | 경막외 신경성형술, epidural neuroplasty, percutaneous epidural neuroplasty, PEN, 유착박리술, Racz catheter | 중재적 통증치료 |
| 풍선확장술 | 풍선신경성형술, balloon catheter neuroplasty, balloon decompression, 경막외 풍선확장술 | 중재적 통증치료 |
| 고주파 치료 | 고주파열치료술, radiofrequency ablation, RFA, radiofrequency therapy, 고주파 신경차단술, pulsed radiofrequency, PRF, 내측지 고주파 | 중재적 통증치료 |
| 프롤로 주사 | 프롤로테라피, prolotherapy, 증식치료, 인대강화주사, proliferation therapy | 중재적 통증치료 |
| PRP 주사 | 혈소판 풍부 혈장, platelet-rich plasma, PRP, 자가혈 주사, 자가혈 치료 | 중재적 통증치료 |
| 통증 주사 | 통증유발점 주사, trigger point injection, TPI, steroid injection, 스테로이드 주사, 국소마취제 주사 | 중재적 통증치료 |
| 성상신경절 차단 | 성상신경절 차단술, stellate ganglion block, SGB, 교감신경 차단, sympathetic block | 중재적 통증치료 |
| 척추후관절 통증 | 후관절 증후군, facet joint syndrome, facet joint pain, 내측지 신경차단, medial branch block, MBB | 척추 통증 |
| 천장관절 통증 | 천장관절 증후군, sacroiliac joint pain, SI joint, 천장관절 차단술, sacroiliac joint injection | 척추 통증 |
| 척추압박골절 | 골다공증성 압박골절, vertebral compression fracture, VCF, 척추체성형술, vertebroplasty, 풍선척추성형술, kyphoplasty | 척추 통증 |
| 무통분만 | 경막외 무통분만, epidural analgesia, labor epidural, 무통주사, 산과마취, obstetric anesthesia | 마취 |
| 전신마취 | general anesthesia, GA, 기관내 삽관, endotracheal intubation, 마취심도, BIS monitoring | 마취 |
| 부위마취 | regional anesthesia, 척추마취, spinal anesthesia, 경막외마취, epidural anesthesia, 신경총 차단, brachial plexus block | 마취 |
| 수면마취 | 진정, sedation, monitored anesthesia care, MAC, 프로포폴, propofol, 의식하 진정 | 마취 |
| 국소마취 | local anesthesia, 리도카인, lidocaine, 국소마취제, local anesthetic | 마취 |
| 수술 후 통증 | 술후 통증, postoperative pain, 자가통증조절, patient-controlled analgesia, PCA, 무통주사 | 마취 |
| 암성 통증 | cancer pain, 암 통증, 마약성 진통제, opioid analgesics, 경피적 척수신경 자극 | 만성 통증 |
| 당뇨병성 신경병증 | 당뇨병성 말초신경병증, diabetic neuropathy, diabetic peripheral neuropathy, 신경병증성 통증, neuropathic pain | 신경병증성 통증 |
| 척추수술후 통증 | 척추수술 실패 증후군, failed back surgery syndrome, FBSS, post-laminectomy syndrome, 척수자극술, spinal cord stimulation, SCS | 척추 통증 |
| 손발 저림 | paresthesia, 감각이상, 말초신경병증, peripheral neuropathy, 신경포착, nerve entrapment | 신경병증성 통증 |
| 목 디스크 협착 | 경추관 협착증, cervical spinal stenosis, 경추 신경공 협착 | 척추 통증 |
| 이상근 증후군 | piriformis syndrome, 둔부 통증, 이상근 차단 | 근골격 통증 |
| 척추 통증 | 척추질환, spinal pain, 경추부·요추부 통증, axial pain | 척추 통증 |
| 체외충격파 | 체외충격파치료, extracorporeal shock wave therapy, ESWT, 충격파 치료 | 중재적 통증치료 |
| 교감신경 차단 | sympathetic nerve block, 요부 교감신경 차단, lumbar sympathetic block, 내장신경 차단, celiac plexus block | 중재적 통증치료 |
| 척추 경막외 주사 | 경막외 주사, epidural injection, 경막외 스테로이드 주사, epidural steroid injection, C-arm 유도 주사 | 중재적 통증치료 |

## 진료과: 이비인후과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 콧물 | 비루, rhinorrhea, 수양성 비루, 후비루, postnasal drip, 비강 분비물 | 비과 |
| 코막힘 | 비폐색, nasal obstruction, nasal congestion, 비강 폐색, 비충혈 | 비과 |
| 비염 | rhinitis, 알레르기 비염, allergic rhinitis, 혈관운동성 비염, vasomotor rhinitis, 비후성 비염, 위축성 비염 | 비과 |
| 축농증 | 부비동염, sinusitis, 비부비동염, rhinosinusitis, 급성 부비동염, acute rhinosinusitis, 만성 부비동염, chronic rhinosinusitis, CRS, 상악동염 | 비과 |
| 코 안 물혹 | 비용종, nasal polyp, 비용, 부비동 용종, 비강 폴립 | 비과 |
| 코뼈 휘어짐 | 비중격만곡증, deviated nasal septum, nasal septal deviation, 비중격교정술, septoplasty | 비과 |
| 코피 | 비출혈, epistaxis, 전방 비출혈, 후방 비출혈, 키셀바흐 영역, Kiesselbach's plexus, 비강 패킹 | 비과 |
| 코골이 | snoring, 코골이 수술, 구개수구개인두성형술, UPPP, uvulopalatopharyngoplasty, 연구개 수술 | 수면호흡 |
| 수면무호흡 | 수면무호흡증, obstructive sleep apnea, OSA, 폐쇄성 수면무호흡, 수면다원검사, polysomnography, 양압기, CPAP | 수면호흡 |
| 콧속 살 | 하비갑개비대, 비갑개 비대, inferior turbinate hypertrophy, turbinate hypertrophy, 비갑개 절제술, turbinoplasty, 고주파 비갑개 축소술 | 비과 |
| 후각저하 | 후각장애, anosmia, hyposmia, 嗅覺障碍, 후각감퇴, olfactory dysfunction, 후각검사 | 비과 |
| 중이염 | otitis media, 급성 중이염, acute otitis media, 삼출성 중이염, otitis media with effusion, OME, 만성 중이염, chronic otitis media | 이과 |
| 외이도염 | otitis externa, 외이염, 외이도 진균증, otomycosis, 귀 습진 | 이과 |
| 고막천공 | 고막 천공, tympanic membrane perforation, 고막성형술, tympanoplasty, 고실성형술, myringoplasty | 이과 |
| 귀에 물참 | 삼출성 중이염, middle ear effusion, 고막 환기관 삽입술, ventilation tube insertion, 고막 튜브, tympanostomy tube | 이과 |
| 난청 | hearing loss, 전음성 난청, conductive hearing loss, 감각신경성 난청, sensorineural hearing loss, 돌발성 난청, sudden sensorineural hearing loss, 노인성 난청, presbycusis | 이과 |
| 이명 | tinnitus, 耳鳴, 귀울림, 이명 재훈련 치료, tinnitus retraining therapy, 이명도검사, tinnitus matching test | 이과 |
| 어지럼증 | 현훈, vertigo, 眩暈, 이석증, 양성 발작성 두위 현훈, BPPV, benign paroxysmal positional vertigo, 전정신경염, vestibular neuritis, 이석치환술, Epley maneuver | 이과 |
| 메니에르병 | 메니에르, Meniere's disease, 내림프수종, endolymphatic hydrops, 회전성 어지럼, 이충만감 | 이과 |
| 귀지 | 이구, cerumen, 이구전색, cerumen impaction, 귀지 제거, 이구 세척 | 이과 |
| 청력검사 | 순음청력검사, pure tone audiometry, 어음청력검사, speech audiometry, 고막운동성검사, tympanometry, 청성뇌간반응검사, ABR, auditory brainstem response, 이음향방사검사, OAE | 이과 |
| 편도염 | tonsillitis, 급성 편도염, acute tonsillitis, 구개편도, 편도비대, tonsillar hypertrophy, 편도절제술, tonsillectomy | 두경부 |
| 아데노이드 | 인두편도, adenoid, 아데노이드 비대, adenoid hypertrophy, 아데노이드 절제술, adenoidectomy | 두경부 |
| 편도결석 | tonsillolith, tonsil stone, 편도와, 편도음와, 편도결석 제거, 구취 | 두경부 |
| 인후통 | 인두염, pharyngitis, 급성 인두염, acute pharyngitis, 후두인두염, 목 통증 | 두경부 |
| 쉰목소리 | 애성, hoarseness, 발성장애, dysphonia, 성대결절, vocal nodule, 성대폴립, vocal polyp, 후두미세수술, laryngomicrosurgery | 음성후두 |
| 후두염 | laryngitis, 급성 후두염, acute laryngitis, 만성 후두염, 역류성 후두염, laryngopharyngeal reflux, LPR | 음성후두 |
| 성대질환 | 성대결절, vocal cord nodule, 성대폴립, vocal cord polyp, 성대마비, vocal cord paralysis, 후두스트로보스코피, stroboscopy, 후두내시경, laryngoscopy | 음성후두 |
| 삼킴곤란 | 연하장애, dysphagia, 嚥下障碍, 연하곤란, 비디오투시연하검사, VFSS | 두경부 |
| 목소리 변화 | 음성장애, voice disorder, 음성검사, 음향분석, 음성치료, voice therapy | 음성후두 |
| 목 멍울 | 경부 종괴, neck mass, cervical mass, 경부 림프절 비대, cervical lymphadenopathy, 경부 초음파 | 두경부 |
| 갑상선 혹 | 갑상선 결절, thyroid nodule, 갑상선 종양, 갑상선 초음파, thyroid ultrasonography, 세침흡인검사, FNA | 두경부 |
| 침샘 질환 | 타액선염, sialadenitis, 타석증, sialolithiasis, 이하선, parotid gland, 악하선, submandibular gland | 두경부 |
| 구내염 | 구강 점막염, stomatitis, 아프타성 구내염, aphthous stomatitis, 구강 궤양 | 두경부 |
| 구취 | 입냄새, halitosis, 구강 악취, 편도결석 관련 구취 | 두경부 |
| 코 알레르기 검사 | 알레르기 피부반응검사, skin prick test, MAST 검사, 특이 IgE 검사, 비강 내시경, nasal endoscopy | 비과 |
| 안면마비 | 말초성 안면신경마비, 벨마비, Bell's palsy, facial nerve palsy, 안면신경, facial nerve | 이과 |
| 귀울림 이충만감 | 이충만감, ear fullness, aural fullness, 이관기능장애, Eustachian tube dysfunction, 이관 | 이과 |
| 물사마귀 같은 귀혹 | 진주종, cholesteatoma, 진주종성 중이염, 유양돌기 절제술, mastoidectomy | 이과 |
| 코성형 기능교정 | 비밸브재건, 기능적 비성형, functional rhinoplasty, 비밸브 협착, nasal valve collapse | 비과 |
| 후두암 의심 | 후두 종양, laryngeal tumor, 성문암, 후두 내시경 조직검사, 경부 CT | 두경부 |
| 사래들림 | 흡인, aspiration, 연하 후 기침, 후두 침투 | 두경부 |
| 코 내시경 | 비내시경, nasal endoscopy, 부비동 내시경수술, FESS, functional endoscopic sinus surgery, 내시경 부비동수술 | 비과 |
| 딸꾹질 같은 목 이물감 | 인두 이물감, globus sensation, globus pharyngeus, 후두인두역류 | 음성후두 |

## 진료과: 안과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 백내장 | cataract, 수정체 혼탁, 노년백내장, senile cataract, 후낭하 백내장, 백내장 수술, 수정체 유화술, phacoemulsification, 인공수정체 삽입술, intraocular lens, IOL | 백내장·수정체 |
| 녹내장 | glaucoma, 개방각 녹내장, open angle glaucoma, 폐쇄각 녹내장, angle closure glaucoma, 정상안압 녹내장, normal tension glaucoma, 시신경 손상, 시신경유두 함몰, 선택적 레이저 섬유주성형술, SLT, 섬유주절제술, trabeculectomy | 녹내장 |
| 안압 | intraocular pressure, IOP, 안압측정, tonometry, 골드만 압평안압계, Goldmann applanation tonometry, 비접촉안압계, non-contact tonometer | 녹내장 |
| 황반변성 | macular degeneration, 나이관련황반변성, age-related macular degeneration, AMD, 건성 황반변성, dry AMD, 습성 황반변성, wet AMD, 맥락막 신생혈관, choroidal neovascularization, 항혈관내피성장인자 주사, anti-VEGF 주사 | 망막 |
| 망막박리 | retinal detachment, 열공성 망막박리, rhegmatogenous retinal detachment, 유리체절제술, vitrectomy, 공막돌륭술, scleral buckling, 망막열공, retinal tear | 망막 |
| 당뇨망막병증 | diabetic retinopathy, 비증식성 당뇨망막병증, 증식성 당뇨망막병증, proliferative diabetic retinopathy, 당뇨황반부종, diabetic macular edema, 범망막광응고술, panretinal photocoagulation, 레이저 광응고술 | 망막 |
| 비문증 | floaters, myodesopsia, 유리체혼탁, vitreous opacity, 날파리증, 후유리체박리, posterior vitreous detachment, PVD | 망막 |
| 눈 안에 뭔가 떠다님 | floaters, 비문증, 유리체 부유물, vitreous floaters | 망막 |
| 망막혈관폐쇄 | retinal vein occlusion, RVO, 망막정맥폐쇄, 망막동맥폐쇄, retinal artery occlusion, 중심망막정맥폐쇄, central retinal vein occlusion, CRVO | 망막 |
| 황반원공 | macular hole, 황반전막, epiretinal membrane, ERM, 황반부종, macular edema | 망막 |
| 라식 | LASIK, laser in situ keratomileusis, 엑시머 레이저, excimer laser, 각막절편, corneal flap, 굴절교정수술, refractive surgery | 시력교정 |
| 라섹 | LASEK, laser assisted sub-epithelial keratomileusis, 표층절제술, PRK, photorefractive keratectomy, 각막상피, corneal epithelium | 시력교정 |
| 스마일라식 | SMILE, small incision lenticule extraction, 각막실질렌즈, lenticule, 리렉스 스마일, ReLEx SMILE | 시력교정 |
| 렌즈삽입술 | ICL, implantable collamer lens, 안내렌즈삽입술, phakic intraocular lens, 유수정체 인공수정체 | 시력교정 |
| 근시 | myopia, nearsightedness, 근시 진행, 고도근시, high myopia, 굴절이상, refractive error | 시력교정 |
| 원시 | hyperopia, farsightedness, 원시안, 굴절이상 | 시력교정 |
| 난시 | astigmatism, 각막난시, corneal astigmatism, 불규칙난시, irregular astigmatism | 시력교정 |
| 노안 | presbyopia, 노안교정, 노안수술, 다초점 인공수정체, multifocal IOL, 조절력 저하 | 시력교정 |
| 안구건조증 | dry eye syndrome, 건성안, dry eye, 눈물막 불안정, tear film instability, 마이봄샘 기능장애, meibomian gland dysfunction, MGD, 눈물층 검사, 쉬르머 검사, Schirmer test | 안구표면 |
| 결막염 | conjunctivitis, 알레르기결막염, allergic conjunctivitis, 유행성각결막염, epidemic keratoconjunctivitis, 바이러스결막염, viral conjunctivitis, 세균결막염 | 안구표면 |
| 충혈 | ocular hyperemia, conjunctival injection, 결막충혈, 안구충혈 | 안구표면 |
| 익상편 | pterygium, 군날개, 결막증식, 익상편 절제술, pterygium excision, 자가결막이식술, conjunctival autograft | 안구표면 |
| 다래끼 | hordeolum, 맥립종, stye, 산립종, chalazion, 다래끼 절개술, incision and curettage | 안검·안성형 |
| 눈꺼풀염 | blepharitis, 안검염, 전안검염, anterior blepharitis, 후안검염, posterior blepharitis | 안검·안성형 |
| 눈꺼풀 처짐 | ptosis, 안검하수, blepharoptosis, 안검하수 교정술, ptosis repair, 상안검거근, levator muscle | 안검·안성형 |
| 안검내반 | entropion, 속눈썹 찔림, 안검외반, ectropion, 눈꺼풀 교정술 | 안검·안성형 |
| 눈물흘림 | epiphora, 유루증, 코눈물관 폐쇄, nasolacrimal duct obstruction, NLDO, 눈물길 검사, 누관 개통술, dacryocystorhinostomy, DCR | 눈물기관 |
| 사시 | strabismus, 내사시, esotropia, 외사시, exotropia, 사시 교정술, strabismus surgery, 안근 수술, extraocular muscle surgery | 소아·사시 |
| 약시 | amblyopia, lazy eye, 약시 치료, 가림치료, occlusion therapy, 굴절성 약시 | 소아·사시 |
| 소아 시력 | pediatric ophthalmology, 소아안과, 굴절검사, 조절마비 굴절검사, cycloplegic refraction, 시력발달 | 소아·사시 |
| 각막염 | keratitis, 각막궤양, corneal ulcer, 세균각막염, bacterial keratitis, 헤르페스각막염, herpetic keratitis | 각막 |
| 원추각막 | keratoconus, 각막확장증, corneal ectasia, 각막교차결합술, corneal collagen cross-linking, CXL, 각막링삽입술, intrastromal corneal ring | 각막 |
| 각막혼탁 | corneal opacity, 각막반흔, corneal scar, 각막이식, corneal transplantation, keratoplasty, 전층각막이식, penetrating keratoplasty | 각막 |
| 포도막염 | uveitis, 전포도막염, anterior uveitis, 홍채염, iritis, 홍채모양체염, iridocyclitis, 후포도막염, posterior uveitis | 포도막·염증 |
| 시신경염 | optic neuritis, 시신경병증, optic neuropathy, 허혈성 시신경병증, ischemic optic neuropathy | 신경안과 |
| 복시 | diplopia, double vision, 단안복시, monocular diplopia, 양안복시, binocular diplopia | 신경안과 |
| 눈부심 | photophobia, 광과민, 눈부심 증상, glare | 안구표면 |
| 안검경련 | blepharospasm, 눈꺼풀 떨림, eyelid twitching, 안면경련, 보툴리눔 독소 주사, botulinum toxin injection | 안검·안성형 |
| 비립종 | milia, 한관종, syringoma, 황색종, xanthelasma, 눈가 결절 | 안검·안성형 |
| 시야검사 | visual field test, perimetry, 자동시야검사, automated perimetry, 험프리 시야검사, Humphrey visual field | 검사 |
| 안저검사 | fundus examination, 안저촬영, fundus photography, 산동검사, dilated fundus exam, 빛간섭단층촬영, optical coherence tomography, OCT | 검사 |
| 시력검사 | visual acuity test, 굴절검사, refraction test, 자동굴절검사, autorefraction, 교정시력 | 검사 |
| 각막지형도검사 | corneal topography, 각막곡률검사, keratometry, 각막두께검사, pachymetry, 전안부 검사, anterior segment analysis | 검사 |
| 형광안저혈관조영술 | fluorescein angiography, FAG, 인도시아닌그린 혈관조영, indocyanine green angiography, ICG | 검사 |
| 눈물층검사 | tear break-up time, TBUT, 눈물막 파괴시간, 쉬르머 검사, Schirmer test | 검사 |
| 눈 안에 출혈 | vitreous hemorrhage, 유리체출혈, 결막하출혈, subconjunctival hemorrhage, 망막출혈, retinal hemorrhage | 망막 |
| 비정상 안구돌출 | exophthalmos, proptosis, 안구돌출증, 갑상선눈병증, thyroid eye disease, Graves orbitopathy | 안와·신경안과 |
| 눈 통증 | ocular pain, eye pain, 안구통증, 각막미란, corneal erosion, 각막상피결손 | 안구표면 |
| 각막이물 | corneal foreign body, 이물제거술, 각막찰과상, corneal abrasion, 결막이물 | 각막 |

## 진료과: 치과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 충치 | 치아우식증, 치아우식, dental caries, tooth decay, 우식, caries | 보존치료 |
| 충치 치료 | 우식 치료, 충전, filling, 레진 충전, composite filling, 수복치료, restoration | 보존치료 |
| 이가 시려요 | 치아 지각과민, 상아질 지각과민증, dentin hypersensitivity, 지각과민, 냉온자극 통증 | 보존치료 |
| 치통 | 치아 통증, toothache, odontalgia, 교합통, 자발통 | 보존치료 |
| 신경치료 | 근관치료, root canal treatment, endodontic treatment, 치수치료, 근관 충전, 치수 제거 | 근관치료 |
| 치수염 | pulpitis, 치수 염증, 가역성 치수염, 비가역성 치수염, irreversible pulpitis, 치수 괴사, pulp necrosis | 근관치료 |
| 치아 농양 | 치근단 농양, periapical abscess, 치성 농양, dental abscess, 치근단 병변, 치근단 치주염, apical periodontitis | 근관치료 |
| 잇몸병 | 치주질환, periodontal disease, gum disease, 풍치, 치주염, periodontitis | 치주치료 |
| 잇몸 염증 | 치은염, gingivitis, 치은 염증, 잇몸 출혈, gingival inflammation | 치주치료 |
| 치주염 | periodontitis, 치조골 흡수, alveolar bone loss, 치주낭, periodontal pocket, 만성 치주염 | 치주치료 |
| 잇몸이 부었어요 | 치은 종창, 잇몸 부종, gingival swelling, 치은 비대, gingival hyperplasia | 치주치료 |
| 스케일링 | 치석 제거, scaling, 치면세마, prophylaxis, 치주 스케일링 | 치주치료 |
| 잇몸 치료 | 치주치료, 치근활택술, root planing, 치은 소파술, curettage, 치주 소파술, SRP, scaling and root planing | 치주치료 |
| 잇몸 수술 | 치주판막술, flap surgery, 치은절제술, gingivectomy, 치주성형술, 골이식술, bone graft, 조직유도재생술, GTR | 치주치료 |
| 치석 | 치태, dental plaque, calculus, tartar, 치은연하 치석, subgingival calculus | 치주치료 |
| 임플란트 | 치과 임플란트, dental implant, 인공치근, 골융합, osseointegration, fixture, 픽스처, 임플란트 보철 | 임플란트 |
| 뼈이식 | 골이식, bone graft, 상악동거상술, sinus lift, GBR, 골유도재생술, 치조골 이식 | 임플란트 |
| 사랑니 | 제3대구치, 지치, wisdom tooth, third molar, 매복치, impacted tooth | 구강악안면외과 |
| 사랑니 발치 | 지치 발치, 발치, extraction, tooth extraction, exodontia, 매복치 발치, 수술 발치 | 구강악안면외과 |
| 발치 | 이 뽑기, tooth extraction, exodontia, 외과적 발치, surgical extraction | 구강악안면외과 |
| 사랑니 염증 | 지치주위염, pericoronitis, 치관주위염, 사랑니 주위 염증 | 구강악안면외과 |
| 치아교정 | 교정치료, orthodontics, orthodontic treatment, 치열교정, 브라켓, bracket, 와이어 교정, braces | 치과교정 |
| 부정교합 | malocclusion, 교합 이상, 덧니, 총생, crowding, 개방교합, open bite, 과개교합, deep bite | 치과교정 |
| 투명교정 | 투명 장치 교정, clear aligner, 인비절라인, Invisalign, 투명 얼라이너 | 치과교정 |
| 주걱턱 | 하악전돌, 반대교합, 전치부 반대교합, anterior crossbite, 골격성 III급 부정교합, mandibular prognathism | 치과교정 |
| 돌출입 | 상악전돌, 양악전돌, bimaxillary protrusion, 전치 돌출 | 치과교정 |
| 양악수술 | 악교정수술, orthognathic surgery, 양악 수술, 골격성 부정교합 수술, 악골 수술 | 구강악안면외과 |
| 크라운 | 치아 보철, crown, 치관 수복물, 지르코니아 크라운, zirconia crown, PFM, 금관 | 보철치료 |
| 브릿지 | 치아 브릿지, dental bridge, 고정성 가공의치, fixed partial denture, 지대치 | 보철치료 |
| 틀니 | 의치, denture, 총의치, complete denture, 부분의치, partial denture, removable prosthesis | 보철치료 |
| 라미네이트 | 치아 라미네이트, veneer, laminate veneer, 포세린 라미네이트, porcelain veneer, 치면 부착 | 미용치과 |
| 치아미백 | 미백, teeth whitening, bleaching, 전문가 미백, 자가미백, 치아 표백 | 미용치과 |
| 인레이 | inlay, onlay, 온레이, 간접 수복, 세라믹 인레이, ceramic inlay, 골드 인레이 | 보존치료 |
| 레진 | 복합레진, composite resin, 레진 충전, 광중합 레진, tooth-colored filling, 심미 충전 | 보존치료 |
| 구내염 | stomatitis, 구강 점막 염증, 아프타성 구내염, aphthous ulcer, 재발성 아프타, 구강 궤양 | 구강내과 |
| 입냄새 | 구취, halitosis, bad breath, 구강 악취 | 구강내과 |
| 입안이 헐었어요 | 구강 궤양, oral ulcer, 점막 미란, 구강 점막 병변, 혀 통증, glossitis | 구강내과 |
| 턱관절 장애 | 턱관절 질환, TMJ disorder, temporomandibular joint disorder, TMD, 악관절 장애, 측두하악관절 장애 | 구강내과 |
| 턱에서 소리나요 | 턱관절 잡음, 관절 잡음, clicking, crepitus, 개구장애, 악관절 동통 | 구강내과 |
| 이갈이 | 이악물기, bruxism, 교합력 과다, 야간 이갈이, 이갈이 장치, occlusal splint | 구강내과 |
| 구강암 | oral cancer, 구강 편평세포암, oral squamous cell carcinoma, 설암, tongue cancer, 구강 악성종양 | 구강악안면외과 |
| 혀가 하얘요 | 설태, 구강 칸디다증, oral candidiasis, 백반증, leukoplakia, 구강 점막 백색 병변 | 구강내과 |
| 실란트 | 치아 홈메우기, 치면열구전색, pit and fissure sealant, 예방 충전, 구치부 실란트 | 소아치과 |
| 불소도포 | 불소 도포, fluoride application, topical fluoride, 불소 바니쉬, fluoride varnish, 우식 예방 | 소아치과 |
| 소아 충치 | 유치 우식, 젖니 충치, early childhood caries, 유치 충전, 유치 신경치료, 치수절단술, pulpotomy | 소아치과 |
| 치아 깨짐 | 치아 파절, tooth fracture, crack tooth, 균열치, cracked tooth syndrome, 치관 파절 | 보존치료 |
| 치아 외상 | 치아 탈구, tooth luxation, 치아 함입, 치아 정출, avulsion, 외상성 치아 손상, dental trauma | 구강악안면외과 |
| 잇몸 내려앉음 | 치은 퇴축, gingival recession, 치근 노출, 잇몸 退縮, 치주 퇴축 | 치주치료 |
| 치아 변색 | 변색치, tooth discoloration, 내인성 변색, 외인성 착색, 테트라사이클린 착색 | 미용치과 |
| 구강건조증 | 입마름, xerostomia, dry mouth, 타액분비 저하, 구강 건조 | 구강내과 |
| 치근단절제술 | 치근단 절제술, apicoectomy, 치근단 수술, 역충전, periradicular surgery | 근관치료 |
| 치아 재식술 | 의도적 재식술, intentional replantation, 치아 재식, tooth replantation | 근관치료 |
| 구강검진 | 치과 검진, oral examination, 구강 정기검진, 치주낭 측정, probing |  |
| 치과 엑스레이 | 파노라마, panorama, panoramic radiograph, 치근단 방사선, periapical radiograph, 치과 CT, CBCT, 콘빔 CT |  |
| 혀 통증 | 설통, glossodynia, 구강작열감 증후군, burning mouth syndrome, 설염, glossitis | 구강내과 |
| 치은 출혈 | 잇몸 출혈, gingival bleeding, 양치 시 출혈, 치주 출혈, bleeding on probing | 치주치료 |

## 진료과: 내과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 소화불량 | 기능성 소화불량, functional dyspepsia, dyspepsia, 상복부 불쾌감, 포만감 | 소화기내과 |
| 속쓰림 | 역류성 식도염, 위식도역류질환, GERD, gastroesophageal reflux disease, reflux esophagitis, 위산 역류 | 소화기내과 |
| 위염 | gastritis, 급성 위염, 만성 위염, 표재성 위염, 위축성 위염, atrophic gastritis, 헬리코박터 파일로리, Helicobacter pylori | 소화기내과 |
| 위궤양 | gastric ulcer, 소화성 궤양, peptic ulcer, 위·십이지장 궤양, 십이지장 궤양, duodenal ulcer | 소화기내과 |
| 과민성 대장 증후군 | 과민성 장증후군, irritable bowel syndrome, IBS, 기능성 장질환 | 소화기내과 |
| 변비 | constipation, 기능성 변비, 만성 변비 | 소화기내과 |
| 설사 | diarrhea, 급성 설사, 만성 설사, 장염, 감염성 장염, enteritis | 소화기내과 |
| 대장 용종 | 대장 폴립, colon polyp, 선종, adenoma, 용종 절제술, polypectomy | 소화기내과 |
| 염증성 장질환 | 궤양성 대장염, ulcerative colitis, 크론병, Crohn's disease, inflammatory bowel disease, IBD | 소화기내과 |
| 지방간 | 비알코올성 지방간, non-alcoholic fatty liver disease, NAFLD, 지방간염, steatohepatitis, 간 효소 수치 상승 | 소화기내과 |
| 간염 | hepatitis, B형 간염, hepatitis B, C형 간염, hepatitis C, 바이러스성 간염, 간경변, liver cirrhosis | 소화기내과 |
| 담석 | 담낭 결석, cholelithiasis, gallstone, 담낭염, cholecystitis, 담관 결석 | 소화기내과 |
| 췌장염 | pancreatitis, 급성 췌장염, 만성 췌장염, amylase, lipase | 소화기내과 |
| 위내시경 | 상부 위장관 내시경, esophagogastroduodenoscopy, EGD, gastroscopy, 수면 내시경, 조직검사, biopsy | 소화기내과 |
| 대장내시경 | colonoscopy, 하부 위장관 내시경, 대장 용종 절제, 수면 대장내시경 | 소화기내과 |
| 고혈압 | hypertension, 본태성 고혈압, essential hypertension, 혈압 측정, blood pressure, 2차성 고혈압 | 순환기내과 |
| 협심증 | angina pectoris, 안정형 협심증, 불안정 협심증, 허혈성 심질환, ischemic heart disease, 관상동맥질환, coronary artery disease | 순환기내과 |
| 심근경색 | myocardial infarction, 심장마비, 급성 심근경색, acute myocardial infarction, AMI, ST분절 상승 심근경색, STEMI | 순환기내과 |
| 부정맥 | arrhythmia, 심방세동, atrial fibrillation, 심실 부정맥, ventricular arrhythmia, 기외수축, 서맥, bradycardia, 빈맥, tachycardia | 순환기내과 |
| 심부전 | heart failure, 울혈성 심부전, congestive heart failure, CHF, 좌심실 기능 저하 | 순환기내과 |
| 심장 두근거림 | 심계항진, palpitation, 두근거림 | 순환기내과 |
| 고지혈증 | 이상지질혈증, dyslipidemia, hyperlipidemia, 고콜레스테롤혈증, LDL 콜레스테롤, 중성지방, triglyceride | 순환기내과 |
| 심전도 검사 | electrocardiogram, ECG, EKG, 12유도 심전도, 홀터 검사, Holter monitoring, 24시간 활동 심전도 | 순환기내과 |
| 심장 초음파 | echocardiography, echocardiogram, 경흉부 심초음파, TTE, 심장 판막 검사 | 순환기내과 |
| 관상동맥 조영술 | coronary angiography, CAG, 심혈관 조영, 스텐트 삽입술, stent, 관상동맥 중재술, PCI | 순환기내과 |
| 천식 | asthma, 기관지 천식, bronchial asthma, 알레르기성 천식, 기도 과민성, 흡입기, inhaler | 호흡기내과 |
| 만성폐쇄성폐질환 | chronic obstructive pulmonary disease, COPD, 폐기종, emphysema, 만성 기관지염, chronic bronchitis | 호흡기내과 |
| 폐렴 | pneumonia, 지역사회 획득 폐렴, community-acquired pneumonia, 흡인성 폐렴, 세균성 폐렴 | 호흡기내과 |
| 기관지염 | bronchitis, 급성 기관지염, 기관지 확장증, bronchiectasis | 호흡기내과 |
| 만성 기침 | cough, chronic cough, 객담, 가래, sputum, 후비루 | 호흡기내과 |
| 결핵 | tuberculosis, TB, 폐결핵, pulmonary tuberculosis, 잠복결핵, latent tuberculosis infection, LTBI | 호흡기내과 |
| 수면무호흡증 | obstructive sleep apnea, OSA, 폐쇄성 수면무호흡, 코골이, 수면다원검사, polysomnography | 호흡기내과 |
| 폐기능 검사 | pulmonary function test, PFT, spirometry, 폐활량 측정 | 호흡기내과 |
| 당뇨병 | diabetes mellitus, 제2형 당뇨병, type 2 diabetes, 당화혈색소, HbA1c, 공복 혈당, fasting glucose, 인슐린, insulin | 내분비내과 |
| 갑상선 기능항진증 | hyperthyroidism, 그레이브스병, Graves' disease, 갑상선 호르몬, thyroid hormone, TSH, T3, T4 | 내분비내과 |
| 갑상선 기능저하증 | hypothyroidism, 하시모토 갑상선염, Hashimoto's thyroiditis, 갑상선 자가항체 | 내분비내과 |
| 갑상선 결절 | thyroid nodule, 갑상선 초음파, thyroid ultrasound, 미세침 흡인 세포검사, fine needle aspiration, FNA | 내분비내과 |
| 골다공증 | osteoporosis, 골밀도 검사, bone mineral density, BMD, DEXA, 골감소증, osteopenia | 내분비내과 |
| 비만 | obesity, 체질량지수, body mass index, BMI, 대사증후군, metabolic syndrome | 내분비내과 |
| 부신 질환 | adrenal disorder, 쿠싱 증후군, Cushing's syndrome, 부신피질 호르몬, cortisol | 내분비내과 |
| 만성 콩팥병 | 만성 신부전, chronic kidney disease, CKD, 사구체 여과율, glomerular filtration rate, GFR, 크레아티닌, creatinine | 신장내과 |
| 급성 신부전 | acute kidney injury, AKI, 신기능 저하, 혈액투석, hemodialysis | 신장내과 |
| 단백뇨 | proteinuria, 혈뇨, hematuria, 사구체신염, glomerulonephritis, 신증후군, nephrotic syndrome | 신장내과 |
| 요로결석 | 신장결석, nephrolithiasis, urolithiasis, kidney stone, 요관결석 | 신장내과 |
| 투석 | dialysis, 혈액투석, hemodialysis, 복막투석, peritoneal dialysis, 동정맥루 | 신장내과 |
| 빈혈 | anemia, 철결핍성 빈혈, iron deficiency anemia, 헤모글로빈, hemoglobin, 혈색소, 거대적아구성 빈혈 | 혈액종양내과 |
| 백혈병 | leukemia, 급성 골수성 백혈병, acute myeloid leukemia, AML, 급성 림프구성 백혈병, ALL | 혈액종양내과 |
| 림프종 | lymphoma, 호지킨 림프종, Hodgkin lymphoma, 비호지킨 림프종, non-Hodgkin lymphoma | 혈액종양내과 |
| 혈소판 감소증 | thrombocytopenia, 혈소판, platelet, 출혈 경향, 응고 검사 | 혈액종양내과 |
| 항암 치료 | 항암화학요법, chemotherapy, 표적치료, targeted therapy, 면역항암제, immunotherapy | 혈액종양내과 |
| 통풍 | gout, 고요산혈증, hyperuricemia, 요산, uric acid, 통풍성 관절염, gouty arthritis | 류마티스내과 |
| 류마티스 관절염 | rheumatoid arthritis, RA, 류마티스 인자, rheumatoid factor, anti-CCP, 자가면역질환, autoimmune disease | 류마티스내과 |
| 루푸스 | 전신홍반루푸스, systemic lupus erythematosus, SLE, 항핵항체, ANA | 류마티스내과 |
| 강직성 척추염 | ankylosing spondylitis, AS, HLA-B27, 척추 관절병증, spondyloarthritis | 류마티스내과 |
| 퇴행성 관절염 | 골관절염, osteoarthritis, OA, 관절 연골 | 류마티스내과 |
| 감기 | 상기도 감염, upper respiratory infection, URI, 급성 비인두염, 감기 몸살 | 감염내과 |
| 독감 | 인플루엔자, influenza, flu, 독감 예방접종, influenza vaccine | 감염내과 |
| 요로감염 | urinary tract infection, UTI, 방광염, cystitis, 신우신염, pyelonephritis | 감염내과 |
| 패혈증 | sepsis, 균혈증, bacteremia, 혈액 배양, blood culture | 감염내과 |
| 예방접종 | 백신, vaccination, vaccine, 면역, immunization, 성인 예방접종 | 감염내과 |
| 알레르기 비염 | allergic rhinitis, 비염, 재채기, 코막힘, 알레르기 검사, allergy test | 알레르기내과 |
| 두드러기 | urticaria, 만성 두드러기, chronic urticaria, 혈관부종, angioedema | 알레르기내과 |
| 아나필락시스 | anaphylaxis, 과민반응, hypersensitivity, 에피네프린, epinephrine | 알레르기내과 |
| 복통 | abdominal pain, 복부 통증, 상복부 통증, 하복부 통증 | 소화기내과 |
| 구토 | vomiting, 오심, 메스꺼움, nausea, 구역 | 소화기내과 |
| 어지럼증 | dizziness, 현기증, 기립성 저혈압, orthostatic hypotension |  |
| 만성 피로 | fatigue, 전신 쇠약, 무기력 |  |
| 발열 | fever, 발열 검사, 원인 불명 발열, fever of unknown origin, FUO | 감염내과 |
| 건강검진 | health checkup, 종합검진, 혈액검사, blood test, 소변검사, urinalysis |  |
| 복부 초음파 | abdominal ultrasound, 복부 초음파 검사, 간 초음파, 복부 CT | 소화기내과 |
| 체중 감소 | weight loss, 체중 변화, 원인 미상 체중 감소 |  |
| 황달 | jaundice, 빌리루빈, bilirubin, 담즙 정체 | 소화기내과 |
| 부종 | edema, 하지 부종, 전신 부종, 체액 저류 |  |

## 진료과: 가정의학과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 고혈압 | hypertension, HTN, 본태성 고혈압, 혈압 관리, 수축기 혈압, 이완기 혈압, blood pressure | 만성질환 관리 |
| 당뇨 | 당뇨병, diabetes mellitus, 제2형 당뇨병, type 2 diabetes, T2DM, 혈당 관리, 공복혈당, 당화혈색소, HbA1c, 인슐린 저항성, insulin resistance | 만성질환 관리 |
| 고지혈증 | 이상지질혈증, dyslipidemia, hyperlipidemia, 고콜레스테롤혈증, hypercholesterolemia, 고중성지방혈증, hypertriglyceridemia, LDL 콜레스테롤, HDL 콜레스테롤, 중성지방, triglyceride | 만성질환 관리 |
| 대사증후군 | metabolic syndrome, 복부비만, insulin resistance, 내장지방, 대사이상, 심혈관 위험인자 | 만성질환 관리 |
| 비만 | obesity, 체질량지수, BMI, 과체중, overweight, 복부비만, abdominal obesity, 내장지방, 체성분 분석, 비만 클리닉 | 비만·체중관리 |
| 체중감량 | 체중 관리, weight management, weight loss, 식이요법, diet therapy, 식욕억제제, appetite suppressant, 비만 약물치료, 체성분 검사 | 비만·체중관리 |
| 건강검진 | health checkup, health screening, 종합검진, comprehensive medical examination, 정기검진, 건강검진센터, 검진 프로그램, 국가건강검진, screening test | 건강검진·예방 |
| 예방접종 | vaccination, immunization, 독감 예방접종, influenza vaccine, 폐렴구균 백신, pneumococcal vaccine, 대상포진 백신, zoster vaccine, 파상풍 백신, Tdap, 간염 백신, hepatitis vaccine | 건강검진·예방 |
| 독감 | 인플루엔자, influenza, flu, 독감 검사, 독감 예방접종, 항바이러스제, oseltamivir, 발열 | 급성 일차진료 |
| 감기 | common cold, 상기도감염, upper respiratory infection, URI, 급성 비인두염, acute nasopharyngitis, 콧물, 기침, cough, 인후통, sore throat | 급성 일차진료 |
| 몸살 | 전신 근육통, myalgia, 발열, fever, 오한, chills, flu-like symptoms, 피로감 | 급성 일차진료 |
| 기침 | cough, 급성 기침, 만성 기침, chronic cough, 객담, sputum, 기관지염, bronchitis | 급성 일차진료 |
| 인후통 | 목 통증, sore throat, 인두염, pharyngitis, 편도염, tonsillitis, 연하통 | 급성 일차진료 |
| 발열 | 열, fever, 고열, 발열 평가, 미열, 체온 상승, pyrexia | 급성 일차진료 |
| 소화불량 | dyspepsia, indigestion, 기능성 소화불량, functional dyspepsia, 위장장애, 상복부 불편감, 속쓰림 | 급성 일차진료 |
| 속쓰림 | heartburn, 위산 역류, acid reflux, 위식도역류, GERD, gastroesophageal reflux disease, 제산제 | 급성 일차진료 |
| 설사 | diarrhea, 급성 설사, 장염, gastroenteritis, 위장관염, viral gastroenteritis, 탈수 | 급성 일차진료 |
| 변비 | constipation, 배변장애, 변비약, laxative, 대변 굳기 | 급성 일차진료 |
| 메스꺼움 | 오심, nausea, 구토, vomiting, emesis, 구역감 | 급성 일차진료 |
| 복통 | abdominal pain, 배 통증, 상복부 통증, 하복부 통증, 위경련 | 급성 일차진료 |
| 두통 | headache, 긴장성 두통, tension headache, 편두통, migraine, 두통 평가 | 급성 일차진료 |
| 어지럼증 | 현훈, dizziness, vertigo, 어지럼 평가, 기립성 저혈압, orthostatic hypotension, 균형장애 | 급성 일차진료 |
| 피로 | fatigue, 만성피로, chronic fatigue, 피로감, 무기력, 쇠약감, 권태감 | 증상 평가 |
| 불면증 | insomnia, 수면장애, sleep disorder, 입면 곤란, 수면 위생, sleep hygiene | 증상 평가 |
| 빈혈 | anemia, 철결핍성 빈혈, iron deficiency anemia, 헤모글로빈, hemoglobin, 혈색소 수치 | 만성질환 관리 |
| 갑상선 | 갑상선 기능 검사, thyroid function test, 갑상선기능저하증, hypothyroidism, 갑상선기능항진증, hyperthyroidism, TSH, 갑상선 호르몬 | 내분비 |
| 통풍 | gout, 고요산혈증, hyperuricemia, 요산, uric acid, 관절 통증 | 만성질환 관리 |
| 골다공증 | osteoporosis, 골밀도 검사, bone density test, DEXA, 골감소증, osteopenia, 골절 위험 | 노인의학 |
| 금연 | smoking cessation, 니코틴 의존, nicotine dependence, 니코틴 대체요법, nicotine replacement therapy, 바레니클린, varenicline, 금연 클리닉 | 생활습관 의학 |
| 수액 | 수액 치료, intravenous fluid therapy, IV therapy, 영양수액, 비타민 수액, 링거, 수액주사 | 영양·수액 |
| 영양제 | nutritional supplement, 비타민 주사, vitamin injection, 비타민D, vitamin D, 마이어스 칵테일, 영양 상담 | 영양·수액 |
| 비타민D 부족 | vitamin D deficiency, 비타민D 결핍, 비타민D 검사, 25-hydroxyvitamin D, 비타민D 주사 | 영양·수액 |
| 고령자 건강관리 | 노인의학, geriatrics, 노쇠, frailty, 노인 포괄평가, comprehensive geriatric assessment, 다약제 복용, polypharmacy | 노인의학 |
| 근감소증 | sarcopenia, 근육량 감소, 체성분 분석, 근력 저하, 노쇠 | 노인의학 |
| 치매검사 | 인지기능 검사, cognitive function test, MMSE, 경도인지장애, mild cognitive impairment, 치매 선별검사 | 노인의학 |
| 우울감 | 우울증, depression, 우울 선별검사, PHQ-9, 기분장애, 불안, anxiety | 증상 평가 |
| 간수치 | 간기능 검사, liver function test, LFT, AST, ALT, 지방간, fatty liver, 간 효소 | 만성질환 관리 |
| 지방간 | fatty liver, 비알코올성 지방간, non-alcoholic fatty liver disease, NAFLD, 간 초음파, 지방간염 | 만성질환 관리 |
| 콩팥기능 | 신기능 검사, renal function test, 사구체여과율, eGFR, 크레아티닌, creatinine, 만성콩팥병, chronic kidney disease | 만성질환 관리 |
| 대상포진 | herpes zoster, shingles, 대상포진 백신, 수두대상포진바이러스, 신경통, postherpetic neuralgia | 급성 일차진료 |
| 알레르기 | allergy, 알레르기 비염, allergic rhinitis, 두드러기, urticaria, 알레르기 검사, 항히스타민제 | 급성 일차진료 |
| 관절통 | arthralgia, joint pain, 골관절염, osteoarthritis, 퇴행성 관절염, 근골격계 통증 | 증상 평가 |
| 요통 | 허리 통증, back pain, low back pain, 근막통증, 요추 통증 | 증상 평가 |
| 심전도검사 | electrocardiogram, ECG, EKG, 부정맥, arrhythmia, 심전도 측정 | 건강검진·예방 |
| 흉부엑스레이 | chest X-ray, 흉부 방사선, 폐 검사, 흉부 촬영, CXR | 건강검진·예방 |
| 복부초음파 | abdominal ultrasound, 복부 초음파 검사, 간 초음파, 담낭 검사, sonography | 건강검진·예방 |
| 위내시경 | gastroscopy, 상부위장관내시경, esophagogastroduodenoscopy, EGD, 수면내시경 | 건강검진·예방 |
| 혈액검사 | blood test, 혈액 검사, CBC, complete blood count, 공복 채혈, 기본 혈액검사 | 건강검진·예방 |
| 코로나검사 | COVID-19 검사, PCR 검사, 신속항원검사, rapid antigen test, 코로나19, SARS-CoV-2 | 급성 일차진료 |
| 식욕부진 | anorexia, 입맛 없음, 식욕 저하, 체중 감소, unintentional weight loss | 증상 평가 |
| 부종 | edema, 붓기, 하지 부종, leg swelling, 림프부종 | 증상 평가 |

## 진료과: 소아청소년과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 열 | 발열, 고열, fever, pyrexia, 발열성 질환, febrile illness, 해열제 투여 | 감염·발열 |
| 감기 | 상기도감염, 급성 비인두염, common cold, upper respiratory infection, URI, acute nasopharyngitis, 감기 증후군 | 호흡기 감염 |
| 독감 | 인플루엔자, influenza, flu, 독감 신속항원검사, 항바이러스제, 오셀타미비르 | 호흡기 감염 |
| 중이염 | 급성 중이염, 삼출성 중이염, otitis media, acute otitis media, AOM, otitis media with effusion, 고막 천자 | 이비인후 감염 |
| 폐렴 | 소아 폐렴, pneumonia, 마이코플라스마 폐렴, Mycoplasma pneumoniae, 세균성 폐렴, 흉부 X선 | 호흡기 감염 |
| 기관지염 | 급성 기관지염, acute bronchitis, 천식양 기관지염, 기관지 염증 | 호흡기 감염 |
| 모세기관지염 | bronchiolitis, RSV, 호흡기세포융합바이러스, respiratory syncytial virus, 세기관지염, 네뷸라이저 치료 | 호흡기 감염 |
| 천식 | 소아 천식, pediatric asthma, bronchial asthma, 기관지 천식, 천명, wheezing, 흡입 스테로이드, 폐기능검사, 기관지확장제 | 알레르기·호흡기 |
| 크룹 | croup, 급성 후두기관기관지염, acute laryngotracheobronchitis, 개기침, barking cough, 후두염 | 호흡기 감염 |
| 비염 | 알레르기 비염, allergic rhinitis, 알레르기성 비염, 비결막염, allergic rhinoconjunctivitis, 항히스타민제, 알레르기 검사 | 알레르기·호흡기 |
| 축농증 | 부비동염, sinusitis, rhinosinusitis, 급성 부비동염, 만성 부비동염 | 호흡기 감염 |
| 편도염 | 급성 편도염, tonsillitis, 인후두염, pharyngitis, 연쇄구균 인두염, streptococcal pharyngitis, A군 연쇄구균, 신속항원검사 | 호흡기 감염 |
| 수족구 | 수족구병, hand-foot-and-mouth disease, HFMD, 엔테로바이러스, enterovirus, 콕사키바이러스, Coxsackievirus, 구내 수포 | 감염성 발진 |
| 수두 | varicella, chickenpox, 수두대상포진바이러스, varicella-zoster virus, VZV, 수포성 발진, 수두 백신, VAR | 감염성 발진 |
| 홍역 | measles, rubeola, 홍역 바이러스, MMR 백신, Koplik 반점, 발진성 질환 | 감염성 발진 |
| 풍진 | rubella, German measles, 풍진 바이러스, MMR, 선천성 풍진 증후군 | 감염성 발진 |
| 볼거리 | 유행성 이하선염, mumps, epidemic parotitis, 이하선 부종, MMR | 감염성 발진 |
| 백일해 | pertussis, whooping cough, Bordetella pertussis, DTaP, Tdap, 경련성 기침 | 예방접종·감염 |
| 성홍열 | scarlet fever, scarlatina, A군 연쇄구균, group A streptococcus, 딸기혀, strawberry tongue | 감염성 발진 |
| 돌발진 | 돌발성 발진, roseola infantum, exanthem subitum, 사람헤르페스바이러스 6형, HHV-6 | 감염성 발진 |
| 장염 | 급성 위장관염, gastroenteritis, acute gastroenteritis, AGE, 바이러스성 장염, 세균성 장염, 수액 치료, 경구 수분 보충 | 소화기 감염 |
| 노로바이러스 | norovirus, 바이러스성 위장염, 노로바이러스 장염, 구토·설사 | 소화기 감염 |
| 로타바이러스 | rotavirus, 로타바이러스 장염, RV, 경구 백신, 영아 설사 | 소화기 감염·예방접종 |
| 설사 | 급성 설사, diarrhea, 수양성 설사, 탈수, dehydration, 경구수액요법, ORS | 소화기 |
| 변비 | 기능성 변비, constipation, functional constipation, 배변장애, 완하제, 변완화제 | 소화기 |
| 구토 | vomiting, emesis, 위식도역류, gastroesophageal reflux, GER, 주기성 구토 | 소화기 |
| 복통 | abdominal pain, 기능성 복통, 재발성 복통, 장간막 림프절염, mesenteric lymphadenitis | 소화기 |
| 영아산통 | 영아 산통, infantile colic, colic, 발작성 보챔, 영아 보챔 | 영유아 건강 |
| 장중첩증 | intussusception, 장겹침증, 표적 징후, target sign, 복부 초음파, 공기 정복 | 소화기 응급 |
| 아토피 | 아토피피부염, atopic dermatitis, eczema, 태열, 보습제, 국소 스테로이드 | 알레르기·피부 |
| 두드러기 | urticaria, hives, 급성 두드러기, 만성 두드러기, 항히스타민제 | 알레르기·피부 |
| 식품알레르기 | 음식 알레르기, food allergy, 경구유발시험, oral food challenge, 특이 IgE, 아나필락시스, anaphylaxis | 알레르기 |
| 기저귀발진 | 기저귀피부염, diaper dermatitis, diaper rash, 칸디다 피부염, 접촉성 피부염 | 영유아 피부 |
| 열성경련 | 열성 경련, febrile seizure, febrile convulsion, 단순 열성경련, 복합 열성경련 | 신경 |
| 경련 | seizure, convulsion, 간질, 뇌전증, epilepsy, 뇌파검사, EEG | 신경 |
| 두통 | headache, 소아 두통, 편두통, migraine, 긴장성 두통 | 신경 |
| 발달지연 | 발달 지연, developmental delay, global developmental delay, 발달평가, 발달선별검사, K-DST | 발달·행동 |
| 자폐 | 자폐스펙트럼장애, autism spectrum disorder, ASD, 사회성 발달, 발달 평가 | 발달·행동 |
| ADHD | 주의력결핍 과잉행동장애, attention deficit hyperactivity disorder, 주의력결핍, 행동평가척도, 인지기능검사 | 발달·행동 |
| 틱 | 틱장애, tic disorder, 운동틱, 음성틱, 뚜렛증후군, Tourette syndrome | 발달·행동 |
| 키성장 | 성장, 저신장, short stature, 성장지연, growth retardation, 성장호르몬, 골연령, bone age, 성장곡선 | 성장·내분비 |
| 성조숙증 | 조기 사춘기, precocious puberty, 사춘기 조발증, 성선자극호르몬, GnRH 검사, 골연령 검사 | 성장·내분비 |
| 비만 | 소아비만, childhood obesity, 체질량지수, BMI, 대사증후군, metabolic syndrome | 성장·내분비 |
| 갑상선 | 갑상선기능저하증, hypothyroidism, 선천성 갑상선기능저하증, congenital hypothyroidism, 갑상선기능검사, TSH | 내분비 |
| 소아당뇨 | 1형 당뇨병, type 1 diabetes mellitus, T1DM, 인슐린 의존성 당뇨, 혈당 검사, 당화혈색소, HbA1c | 내분비 |
| 야뇨증 | nocturnal enuresis, enuresis, 야간 요실금, 주간 요실금, 배뇨장애, 하부요로증상, LUTS | 비뇨·배뇨 |
| 요로감염 | urinary tract infection, UTI, 방광염, cystitis, 신우신염, pyelonephritis, 소변검사, 요배양 | 비뇨 |
| 빈혈 | 철결핍성 빈혈, iron deficiency anemia, IDA, anemia, 혈색소, hemoglobin, 철분 보충 | 혈액 |
| 황달 | 신생아 황달, neonatal jaundice, hyperbilirubinemia, 고빌리루빈혈증, 광선치료, phototherapy, 빌리루빈 검사 | 신생아 |
| 미숙아 | 조산아, premature infant, preterm, 저체중 출생아, low birth weight, 신생아 집중치료 | 신생아 |
| 신생아검사 | 선천성 대사이상 검사, newborn screening, 신생아 선별검사, 청력선별검사, 대사이상 선별 | 신생아 |
| 성장통 | growing pains, 사지통증, 야간 다리 통증, 하지 통증 | 근골격 |
| 가와사키병 | Kawasaki disease, 점막피부림프절증후군, mucocutaneous lymph node syndrome, 관상동맥 이상, 면역글로불린, IVIG, 심초음파 | 전신·면역 |
| 림프절염 | 경부 림프절염, cervical lymphadenitis, lymphadenopathy, 림프절 종대, 목 멍울 | 감염 |
| 농가진 | impetigo, 전염성 농가진, 황색포도알균, Staphylococcus aureus, 화농성 피부감염 | 피부 감염 |
| 결막염 | 유행성 결막염, conjunctivitis, 바이러스성 결막염, 아폴로눈병, 눈곱 | 감염 |
| 구내염 | stomatitis, herpetic gingivostomatitis, 헤르페스 구내염, 아프타성 구내염, aphthous ulcer | 구강 감염 |
| 폐결핵 | 결핵, tuberculosis, TB, BCG, 투베르쿨린 검사, 잠복결핵, latent TB | 감염·예방접종 |
| 예방접종 | vaccination, immunization, 국가예방접종, NIP, DTaP, MMR, Hib, 폐렴구균 백신, B형간염, HepB, A형간염, HepA, 일본뇌염, IPV | 예방접종 |
| 독감예방접종 | 인플루엔자 백신, influenza vaccine, 독감 백신, 계절 독감 접종 | 예방접종 |
| 수면장애 | sleep disorder, 야경증, night terror, 소아 불면, 수면 문제 | 발달·행동 |
| 코피 | 비출혈, epistaxis, nosebleed, 비강 출혈 | 이비인후 |
| 콧물 | 비루, rhinorrhea, 코막힘, nasal congestion, 후비루 | 호흡기 |
| 기침 | cough, 만성 기침, 급성 기침, 객담, 가래 | 호흡기 |
| 인후통 | 목감기, sore throat, pharyngitis, 인두염, 삼킴통 | 호흡기 |
| 탈수 | dehydration, 수분 부족, 수액 치료, fluid therapy, 경구수액요법 | 수분·전해질 |
| 제대탈장 | 배꼽탈장, umbilical hernia, 서혜부 탈장, inguinal hernia | 영유아 건강 |
| 사경 | 선천성 사경, torticollis, congenital muscular torticollis, 흉쇄유돌근, 목 기울임 | 근골격 |
| 잠복고환 | 정류고환, cryptorchidism, undescended testis, 음낭 초음파 | 비뇨 |
| 포경 | 포피, phimosis, 귀두포피염, balanoposthitis | 비뇨 |
| 빈혈검사 | 혈액검사, CBC, complete blood count, 말초혈액도말, 피검사 | 검사 |
| 알레르기검사 | 피부단자검사, skin prick test, MAST 검사, 특이 IgE 검사, 혈청 IgE | 알레르기 검사 |

## 진료과: 산부인과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 자궁근종 | 자궁평활근종, uterine myoma, uterine fibroid, leiomyoma, myoma uteri, 근층내근종, 점막하근종, 장막하근종, 자궁근종절제술, myomectomy | 부인과 종양 |
| 자궁내막증 | endometriosis, 자궁내막조직, 초콜릿낭종, 자궁내막종, endometrioma, 골반자궁내막증, 심부침윤성자궁내막증, deep infiltrating endometriosis | 부인과 종양 |
| 자궁선근증 | 자궁샘근증, adenomyosis, 자궁근층비대, 자궁벽비후 | 부인과 종양 |
| 난소낭종 | ovarian cyst, 난소물혹, 기능성낭종, 기형종, 피지낭종, dermoid cyst, teratoma, 장액성낭종, 점액성낭종, 난소낭종절제술, cystectomy | 부인과 종양 |
| 다낭성난소증후군 | polycystic ovary syndrome, PCOS, 다낭성난소, polycystic ovary, 고안드로겐혈증, hyperandrogenism, 무배란, anovulation | 내분비·생식내분비 |
| 자궁경부암 | cervical cancer, 자궁경부세포진검사, Pap smear, Pap test, 자궁경부세포검사, 질확대경검사, colposcopy, 자궁경부생검, cervical biopsy | 부인과 종양 |
| 자궁경부이형성증 | cervical dysplasia, 자궁경부상피내종양, cervical intraepithelial neoplasia, CIN, 상피내암, carcinoma in situ, 원추절제술, conization, cone biopsy, 자궁경부원추절제술, LEEP, loop electrosurgical excision procedure, 환상투열절제술 | 부인과 종양 |
| 인유두종바이러스 | HPV, human papillomavirus, 사람유두종바이러스, HPV DNA 검사, HPV-DNA testing, 고위험군 HPV, 자궁경부암백신, HPV 백신 | 감염·예방 |
| 자궁경부암 검사 | cervical cancer screening, 자궁경부세포진검사, Pap smear, 액상세포검사, liquid based cytology, ThinPrep, 질확대경검사, colposcopy | 검진·진단 |
| 질염 | vaginitis, 세균성질염, bacterial vaginosis, 칸디다질염, candida vaginitis, 곰팡이질염, 트리코모나스질염, trichomonas vaginitis, 위축성질염, atrophic vaginitis, 질분비물검사 | 감염·염증 |
| 골반염 | pelvic inflammatory disease, PID, 골반염증성질환, 난관염, salpingitis, 자궁부속기염, 골반복막염 | 감염·염증 |
| 성병 | sexually transmitted disease, STD, 성매개감염, sexually transmitted infection, STI, 임질, gonorrhea, 클라미디아, chlamydia, 매독, syphilis, 헤르페스, genital herpes, 곤지름, 콘딜로마, condyloma, 성기사마귀 | 감염·염증 |
| 생리불순 | 월경불순, menstrual irregularity, irregular menstruation, 비정상자궁출혈, abnormal uterine bleeding, 희발월경, oligomenorrhea, 빈발월경, polymenorrhea | 월경·내분비 |
| 무월경 | amenorrhea, 월경없음, 원발성무월경, primary amenorrhea, 속발성무월경, secondary amenorrhea | 월경·내분비 |
| 생리통 | 월경통, dysmenorrhea, 원발성월경통, 속발성월경통, 골반통, pelvic pain | 월경·내분비 |
| 월경과다 | menorrhagia, 과다월경, 비정상출혈, 부정출혈, metrorrhagia, 자궁출혈, uterine bleeding | 월경·내분비 |
| 월경전증후군 | premenstrual syndrome, PMS, 월경전불쾌장애, premenstrual dysphoric disorder, PMDD | 월경·내분비 |
| 폐경 | menopause, 완경, 폐경기, 조기폐경, premature ovarian insufficiency, 조기난소부전, 난소기능저하 | 갱년기·내분비 |
| 갱년기 | climacteric, perimenopause, 폐경이행기, 갱년기증후군, 안면홍조, hot flush, 호르몬치료, hormone replacement therapy, HRT, 여성호르몬검사 | 갱년기·내분비 |
| 자궁탈출 | 자궁탈출증, uterine prolapse, 골반장기탈출증, pelvic organ prolapse, POP, 방광탈출, cystocele, 직장탈출, rectocele, 질벽탈출 | 비뇨부인과·골반저 |
| 요실금 | urinary incontinence, 복압성요실금, stress urinary incontinence, 절박성요실금, urge incontinence, 요실금수술, 중부요도슬링, midurethral sling, TOT, TVT | 비뇨부인과·골반저 |
| 질건조증 | vaginal dryness, 위축성질염, vulvovaginal atrophy, 외음질위축, 질위축, 성교통, dyspareunia | 갱년기·여성성건강 |
| 자궁내막용종 | endometrial polyp, 자궁내막폴립, 자궁내막증식증, endometrial hyperplasia, 자궁경검사, hysteroscopy, 자궁내막소파술 | 부인과 종양 |
| 자궁내막암 | endometrial cancer, 자궁체부암, uterine cancer, 자궁내막생검, endometrial biopsy | 부인과 종양 |
| 난소암 | ovarian cancer, 난소종양, ovarian tumor, 종양표지자, CA-125, tumor marker | 부인과 종양 |
| 임신 | pregnancy, 임신진단, 임신반응검사, 혈액임신검사, beta-hCG, 초기임신, 산전관리, antenatal care, prenatal care | 산과·임신관리 |
| 산전검사 | prenatal test, prenatal screening, 기형아검사, fetal anomaly screening, 목덜미투명대검사, nuchal translucency, NT 검사, 쿼드검사, quad test, 통합선별검사, 임신성당뇨검사, 정밀초음파 | 산과·임신관리 |
| 양수검사 | amniocentesis, 양수천자, 융모막검사, chorionic villus sampling, CVS, 태아염색체검사, fetal karyotyping, NIPT, 비침습산전검사, non-invasive prenatal testing | 산과·임신관리 |
| 초음파검사 | ultrasonography, ultrasound, 질초음파, transvaginal ultrasound, 복부초음파, transabdominal ultrasound, 태아초음파, fetal ultrasound, 정밀초음파, 입체초음파, 3D ultrasound | 검진·진단 |
| 제왕절개 | cesarean section, cesarean delivery, C-section, 제왕절개분만, 자궁절개 | 산과·분만 |
| 자연분만 | vaginal delivery, 정상분만, 질식분만, 무통분만, epidural anesthesia, 회음절개, episiotomy, 유도분만, induction of labor | 산과·분만 |
| 유산 | miscarriage, abortion, 자연유산, spontaneous abortion, 계류유산, missed abortion, 절박유산, threatened abortion, 습관성유산, recurrent pregnancy loss, 소파술, dilatation and curettage, D&C | 산과·임신관리 |
| 자궁외임신 | ectopic pregnancy, 난관임신, tubal pregnancy, 복강내출혈 | 산과·임신관리 |
| 난임 | infertility, 불임, subfertility, 배란유도, ovulation induction, 인공수정, intrauterine insemination, IUI, 시험관아기, 체외수정, in vitro fertilization, IVF, 난소예비력검사, AMH 검사, antimullerian hormone, 난관조영술, hysterosalpingography, HSG | 난임·생식의학 |
| 배란통 | ovulation pain, 중간통, mittelschmerz, 배란일, 배란검사, ovulation test | 월경·내분비 |
| 자궁기형 | uterine anomaly, 선천성자궁기형, 쌍각자궁, bicornuate uterus, 중격자궁, septate uterus, 단각자궁, unicornuate uterus | 생식기 해부·기형 |
| 바르톨린낭종 | Bartholin cyst, 바르톨린샘낭종, Bartholin gland cyst, 바르톨린농양, Bartholin abscess, 조대술, marsupialization | 외음·질 질환 |
| 외음부질환 | vulvar disease, 외음통, vulvodynia, 외음소양증, vulvar pruritus, 외음백반증, lichen sclerosus, 경화태선 | 외음·질 질환 |
| 복강경수술 | laparoscopy, 복강경자궁절제술, laparoscopic hysterectomy, 복강경하근종절제술, 단일공복강경, single-port laparoscopy, 로봇수술, robotic surgery | 부인과 수술 |
| 자궁적출술 | hysterectomy, 자궁절제술, 전자궁절제술, total hysterectomy, 근치적자궁절제술, radical hysterectomy, 복강경자궁절제술, laparoscopic hysterectomy, 질식자궁절제술, vaginal hysterectomy | 부인과 수술 |
| 피임 | contraception, 자궁내장치, intrauterine device, IUD, 미레나, Mirena, 피임시술, 난관결찰술, tubal ligation, 피임주사, 피임제거 | 가족계획·피임 |
| 자궁내막소파술 | dilatation and curettage, D&C, 소파수술, 자궁내막생검, endometrial biopsy | 부인과 수술 |
| 임신중독증 | preeclampsia, 임신성고혈압, gestational hypertension, 자간전증, 자간증, eclampsia, HELLP 증후군 | 산과·고위험임신 |
| 임신성당뇨 | gestational diabetes, 임신성당뇨병, GDM, 당부하검사, glucose tolerance test, OGTT | 산과·고위험임신 |
| 태반조기박리 | placental abruption, 전치태반, placenta previa, 조산, preterm labor, 조기진통, 양막파수, premature rupture of membranes, PROM | 산과·고위험임신 |
| 골반초음파 | pelvic ultrasound, 부인과초음파, 난소초음파, 자궁초음파, 골반자기공명영상, pelvic MRI | 검진·진단 |
| 여성검진 | 여성종합검진, 부인과검진, gynecologic examination, 내진, pelvic examination, 질경검사, speculum examination, 성병검사, STD screening | 검진·진단 |
| 냉대하 | leukorrhea, 질분비물, vaginal discharge, 이상분비물, 냉증, 질분비물검사 | 감염·염증 |
| 골반통 | pelvic pain, 만성골반통, chronic pelvic pain, 하복부통증, 골반울혈증후군 | 부인과 증상 |

## 진료과: 비뇨의학과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 전립선비대증 | 전립선 비대증, 양성전립선비대증, benign prostatic hyperplasia, BPH, 전립선 용적 증가, 하부요로증상, lower urinary tract symptoms, LUTS, 경요도전립선절제술, TURP, transurethral resection of prostate, 홀렙, HoLEP, holmium laser enucleation of prostate, 유로리프트, UroLift, 리줌, Rezum, 수증기 치료, 아쿠아블레이션, Aquablation | 전립선 |
| 전립선염 | prostatitis, 급성 세균성 전립선염, 만성 전립선염, chronic prostatitis, 만성골반통증후군, chronic pelvic pain syndrome, CPPS, 비세균성 전립선염, 전립선 마사지, 회음부 통증 | 전립선 |
| 전립선암 | prostate cancer, 전립선 선암, prostatic adenocarcinoma, PSA, 전립선특이항원, prostate specific antigen, 글리슨 점수, Gleason score, 전립선 생검, prostate biopsy, MRI 융합 표적조직검사, 근치적 전립선절제술, radical prostatectomy, 로봇 전립선절제술, 다빈치 | 비뇨기 종양 |
| 요로결석 | urinary stone, urolithiasis, 신장결석, kidney stone, renal calculus, nephrolithiasis, 요관결석, ureteral stone, 방광결석, bladder stone, 체외충격파쇄석술, ESWL, extracorporeal shock wave lithotripsy, 요관내시경 결석제거술, URS, ureteroscopy, 경피적 신장결석제거술, PCNL, percutaneous nephrolithotomy, 레이저 쇄석술, 요산 결석, 칼슘 결석, 수산화칼슘 | 요로결석 |
| 혈뇨 | hematuria, 육안적 혈뇨, gross hematuria, 현미경적 혈뇨, microscopic hematuria, 소변에 피, 요잠혈, 요분석, urinalysis |  |
| 방광염 | cystitis, 급성 방광염, 간질성 방광염, interstitial cystitis, 방광통증증후군, bladder pain syndrome, 재발성 방광염, 배뇨통, dysuria | 요로감염 |
| 요로감염 | urinary tract infection, UTI, 요로 감염증, 재발성 요로감염, 세균뇨, bacteriuria, 농뇨, pyuria | 요로감염 |
| 신우신염 | pyelonephritis, 급성 신우신염, acute pyelonephritis, 신장 감염, 농신증, pyonephrosis | 요로감염 |
| 요도염 | urethritis, 임균성 요도염, 비임균성 요도염, non-gonococcal urethritis, 클라미디아, Chlamydia, 성매개감염, STI | 요로감염 |
| 요실금 | urinary incontinence, 복압성 요실금, stress urinary incontinence, SUI, 절박성 요실금, urge incontinence, 혼합성 요실금, mixed incontinence, 요실금 슬링수술, TOT, TVT, mid-urethral sling, 골반저근운동, 케겔운동 | 배뇨장애·여성비뇨 |
| 과민성방광 | 과민성 방광, overactive bladder, OAB, 절박뇨, urgency, 빈뇨, frequency, 배뇨근 과활동성, detrusor overactivity, 방광 보톡스, botulinum toxin | 배뇨장애 |
| 빈뇨 | frequency, urinary frequency, 주간 빈뇨, 소변을 자주, 배뇨 횟수 증가 | 배뇨장애 |
| 야간뇨 | 야뇨, nocturia, 밤에 소변, 야간 다뇨 | 배뇨장애 |
| 배뇨장애 | voiding dysfunction, 배뇨 곤란, 잔뇨감, residual urine, 소변 줄기 약화, 약뇨, weak stream, 요역동학검사, urodynamic study, uroflowmetry, 요속검사 | 배뇨장애 |
| 소변이 안 나옴 | 요폐, urinary retention, 급성 요폐, acute urinary retention, 도뇨, catheterization, 자가도뇨, CIC | 배뇨장애 |
| 신경인성방광 | 신경인성 방광, neurogenic bladder, 척수손상 방광, 자가도뇨, clean intermittent catheterization | 배뇨장애 |
| 방광암 | bladder cancer, 방광 요로상피암, urothelial carcinoma, 이행세포암, transitional cell carcinoma, 경요도방광종양절제술, TURBT, transurethral resection of bladder tumor, BCG 방광내주입, 방광경검사 | 비뇨기 종양 |
| 신장암 | kidney cancer, 신세포암, renal cell carcinoma, RCC, 신장 종양, renal mass, 부분신절제술, partial nephrectomy, 근치적 신절제술, radical nephrectomy | 비뇨기 종양 |
| 고환암 | testicular cancer, 고환 종양, 정상피종, seminoma, 비정상피종, non-seminoma, 근치적 고환절제술, radical orchiectomy, 종양표지자, AFP, hCG, LDH | 비뇨기 종양 |
| 발기부전 | erectile dysfunction, ED, 음경 발기 장애, 발기력 저하, 음경 도플러 초음파, penile doppler, PDE5 억제제, 포스포디에스테라제, 음경보형물 삽입술, penile prosthesis, 체외충격파 ESWT, low-intensity shockwave | 남성의학 |
| 조루 | 조루증, premature ejaculation, PE, 사정 조절, 음경배부신경차단술, dorsal nerve neurotomy, ejaculation | 남성의학 |
| 정관수술 | 정관절제술, vasectomy, vas deferens ligation, 남성 피임, 무도(無刀) 정관수술, no-scalpel vasectomy, 정관복원술, vasovasostomy, vasectomy reversal | 남성의학 |
| 포경수술 | circumcision, 포피 절제술, 음경 포피, foreskin, 환상절제술, 포경, phimosis, 감돈포경, paraphimosis | 남성의학 |
| 남성갱년기 | late onset hypogonadism, LOH, 남성호르몬 저하, 테스토스테론, testosterone deficiency, TDS, 남성호르몬 보충, TRT | 남성의학 |
| 남성불임 | male infertility, 정액검사, semen analysis, 무정자증, azoospermia, 희소정자증, oligozoospermia, 정자 채취, TESE, 고환조직 정자추출술 | 남성의학 |
| 정계정맥류 | varicocele, 정삭 정맥류, pampiniform plexus, 정계정맥류 결찰술, varicocelectomy, 현미경하 정계정맥류 절제술, microsurgical varicocelectomy | 남성의학·소아비뇨 |
| 음낭수종 | hydrocele, 음낭 수종, 음낭 부종, 정삭수종, hydrocelectomy, 음낭수종 절제술 | 소아비뇨 |
| 고환통증 | 고환 통증, 음낭 통증, scrotal pain, 고환염, orchitis, 부고환염, epididymitis, 고환꼬임, 고환염전, testicular torsion | 남성생식기 |
| 정류고환 | 잠복고환, 미하강 고환, cryptorchidism, undescended testis, 고환고정술, orchiopexy | 소아비뇨 |
| 야뇨증 | nocturnal enuresis, 소아 야뇨증, 야간 유뇨, enuresis, 데스모프레신, desmopressin, 야뇨 경보기 | 소아비뇨 |
| 요관협착 | ureteral stricture, 요관 협착, 신우요관이행부폐색, UPJ obstruction, ureteropelvic junction obstruction, 수신증, hydronephrosis, 요관부목, ureteral stent, double-J stent | 요로 폐색 |
| 요도협착 | urethral stricture, 요도 협착, 요도확장술, urethral dilation, 요도성형술, urethroplasty, 내시경적 요도절개술, urethrotomy | 요로 폐색 |
| 방광경검사 | 방광내시경, cystoscopy, 방광요도경, cystourethroscopy, 연성 방광경, flexible cystoscope, 비뇨기 내시경 | 검사 |
| 전립선초음파 | 경직장 전립선초음파, transrectal ultrasound, TRUS, 비뇨기 초음파, 신장 초음파, 방광 초음파, 잔뇨 측정 | 검사 |
| PSA검사 | 전립선특이항원 검사, prostate specific antigen, PSA, free PSA, 전립선암 선별검사, 혈액검사 | 검사 |
| 요역동학검사 | urodynamic study, 방광요도기능검사, 요속검사, uroflowmetry, 방광내압측정, cystometry, 잔뇨검사 | 검사 |
| 음경만곡 | 페이로니병, Peyronie's disease, 음경 굴곡, penile curvature, 음경 백막 | 남성의학 |
| 지속발기증 | priapism, 음경 지속 발기, 허혈성 지속발기증 | 남성의학 |
| 부신종양 | adrenal tumor, 부신 선종, adrenal adenoma, 부신절제술, adrenalectomy, 갈색세포종, pheochromocytoma | 비뇨기 종양 |
| 수신증 | hydronephrosis, 신장 수종, 신우 확장, 신장 부종, 요로 폐색 | 요로 폐색 |

## 진료과: 외과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 맹장염 | 충수염, 급성 충수염, appendicitis, acute appendicitis, 충수돌기염, 충수절제술, appendectomy, 복강경 충수절제술, laparoscopic appendectomy | 위장관외과 |
| 탈장 | 서혜부 탈장, 사타구니 탈장, inguinal hernia, hernia, 복벽 탈장, ventral hernia, 배꼽 탈장, 제대 탈장, umbilical hernia, 대퇴 탈장, femoral hernia, 탈장 교정술, hernioplasty, herniorrhaphy, 메쉬 보강술, 감돈 탈장, incarcerated hernia | 탈장외과 |
| 담석 | 담석증, cholelithiasis, gallstone, 담낭결석, 담낭염, cholecystitis, 급성 담낭염, 담낭절제술, cholecystectomy, 복강경 담낭절제술, laparoscopic cholecystectomy, 담관결석, choledocholithiasis | 간담췌외과 |
| 쓸개 | 담낭, gallbladder, 담낭용종, gallbladder polyp, 담낭절제술, cholecystectomy, 담낭염, cholecystitis | 간담췌외과 |
| 치질 | 치핵, hemorrhoid, 내치핵, internal hemorrhoid, 외치핵, external hemorrhoid, 혼합치핵, 치핵절제술, hemorrhoidectomy, 치핵 결찰술, rubber band ligation, PPH, 원형 자동 문합기 치핵수술 | 대장항문외과 |
| 치루 | anal fistula, 항문 누공, 치루 절제술, fistulectomy, fistulotomy, 괄약근 보존술, seton 시술, 복잡치루 | 대장항문외과 |
| 항문농양 | 항문주위농양, perianal abscess, anorectal abscess, 절개 배농, incision and drainage, I&D, 항문선 감염 | 대장항문외과 |
| 치열 | 항문열창, anal fissure, 급성 치열, 만성 치열, 측방 내괄약근 절개술, lateral internal sphincterotomy, 항문 궤양 | 대장항문외과 |
| 변비 | 만성 변비, constipation, 직장류, rectocele, 직장탈, 직장탈출증, rectal prolapse, 변실금, fecal incontinence | 대장항문외과 |
| 대장암 | 결장암, 직장암, colorectal cancer, colon cancer, rectal cancer, 대장 절제술, colectomy, 결장절제술, 직장절제술, 복강경 대장절제술, 저위전방절제술, low anterior resection, LAR | 대장항문외과 |
| 대장용종 | 대장 폴립, colon polyp, 선종, adenoma, 용종 절제술, polypectomy | 대장항문외과 |
| 위암 | gastric cancer, stomach cancer, 위 절제술, gastrectomy, 위아전절제술, subtotal gastrectomy, 위전절제술, total gastrectomy, 복강경 위절제술, laparoscopic gastrectomy, 조기위암, early gastric cancer | 위장관외과 |
| 위궤양 | 위 궤양, gastric ulcer, 소화성 궤양, peptic ulcer, 천공성 궤양, perforated ulcer, 위장관 출혈, GI bleeding | 위장관외과 |
| 장폐색 | 장폐색증, intestinal obstruction, bowel obstruction, ileus, 유착성 장폐색, adhesive obstruction, 소장 절제술, 장 유착 | 위장관외과 |
| 간암 | 간세포암, hepatocellular carcinoma, HCC, liver cancer, 간 절제술, hepatectomy, liver resection, 간엽절제술, 고주파 열치료, radiofrequency ablation, RFA | 간담췌외과 |
| 췌장암 | pancreatic cancer, 췌장 절제술, pancreatectomy, 췌십이지장절제술, 휘플 수술, Whipple operation, pancreaticoduodenectomy, 원위췌장절제술, distal pancreatectomy | 간담췌외과 |
| 췌장염 | pancreatitis, 급성 췌장염, acute pancreatitis, 만성 췌장염, 췌장 가성낭종, pancreatic pseudocyst | 간담췌외과 |
| 갑상선암 | thyroid cancer, 유두암, papillary carcinoma, 갑상선 절제술, thyroidectomy, 갑상선 반절제술, lobectomy, 갑상선 전절제술, total thyroidectomy, 내시경 갑상선 수술, 로봇 갑상선 수술, 경부 림프절 절제술 | 내분비외과 |
| 갑상선결절 | 갑상선 혹, thyroid nodule, 갑상선 종양, 갑상선 낭종, thyroid cyst, 고주파 절제술, radiofrequency ablation, RFA, 미세침흡인검사, FNA, 세침흡인세포검사 | 내분비외과 |
| 유방암 | breast cancer, 유방 절제술, mastectomy, 유방보존술, breast conserving surgery, BCS, 감시림프절 생검, sentinel lymph node biopsy, 유방 재건술, 침윤성 유관암, invasive ductal carcinoma | 유방외과 |
| 유방 혹 | 유방 종양, 유방 양성종양, 섬유선종, fibroadenoma, 유방 낭종, breast cyst, 유방 멍울, 유방 절제 생검, 맘모톰, mammotome, 진공보조 흡인생검 | 유방외과 |
| 유방 통증 | 유방통, mastalgia, 유선염, mastitis, 유방 분비물, nipple discharge, 유관확장증 | 유방외과 |
| 하지정맥류 | 다리 정맥류, 정맥류, varicose vein, 복재정맥 부전, 정맥내 레이저 치료, endovenous laser ablation, EVLA, 고주파 정맥폐쇄술, radiofrequency ablation, 혈관경화요법, sclerotherapy, 정맥 발거술, stripping | 혈관외과 |
| 동맥경화 | 죽상경화증, atherosclerosis, 말초동맥질환, peripheral arterial disease, PAD, 동맥폐색, 혈관우회술, bypass, 혈전증, thrombosis | 혈관외과 |
| 혈관 투석 | 동정맥루, arteriovenous fistula, AV fistula, 투석혈관 조성술, 투석 도관 삽입, 동정맥 인조혈관, AV graft | 혈관외과 |
| 혹 | 지방종, lipoma, 표피낭종, epidermal cyst, 피지낭종, sebaceous cyst, 결절종, ganglion, 피하 종괴, subcutaneous mass, 양성 종양 절제술 | 소외과 |
| 고름 | 농양, abscess, 절개 배농, incision and drainage, 연조직염, cellulitis, 봉와직염, 화농성 감염 | 소외과 |
| 상처 | 열상, laceration, 창상, wound, 봉합, suture, 창상 봉합술, wound closure, 찢어진 상처, 절개 봉합 | 소외과 |
| 화상 | burn, 2도 화상, 3도 화상, 창상 처치, wound dressing, 피부이식, skin graft, 괴사조직 제거술, debridement | 소외과 |
| 욕창 | 압박궤양, pressure ulcer, bedsore, 괴사조직 제거술, debridement, 창상 드레싱 | 소외과 |
| 발톱 | 내성발톱, ingrown toenail, 조갑감입증, onychocryptosis, 발톱 부분 절제술, 발톱주위염, paronychia | 소외과 |
| 맹장 | 충수, appendix, 충수염, appendicitis, 충수절제술, appendectomy | 위장관외과 |
| 대장 게실 | 게실염, diverticulitis, 대장 게실증, diverticulosis, 게실 천공 | 대장항문외과 |
| 비장 | 지라, spleen, 비장 절제술, splenectomy, 비장 손상, splenic injury | 위장관외과 |
| 복막염 | peritonitis, 범발성 복막염, 복강 내 감염, 천공, perforation, 응급 개복술, exploratory laparotomy | 응급외과 |
| 위장관 출혈 | 소화관 출혈, GI bleeding, 토혈, hematemesis, 혈변, melena, 흑색변, 지혈술 | 위장관외과 |
| 역류성 식도염 | 위식도 역류질환, GERD, gastroesophageal reflux disease, 식도열공탈장, hiatal hernia, 위저부주름성형술, fundoplication | 위장관외과 |
| 복통 | abdominal pain, 급성 복증, acute abdomen, 복강경 진단, diagnostic laparoscopy, 장간막 질환 | 응급외과 |
| 교통사고 외상 | 다발성 외상, polytrauma, 복부 외상, abdominal trauma, 장기 손상, 외상성 출혈, 응급 수술 | 외상외과 |
| 복강경 | 복강경 수술, laparoscopy, laparoscopic surgery, 최소침습수술, minimally invasive surgery, 단일통로 복강경, single port, 로봇 수술, robotic surgery |  |
| 내시경 조직검사 | 조직검사, biopsy, 절제 생검, excisional biopsy, 절개 생검, incisional biopsy, 세침흡인, FNA, core needle biopsy |  |
| 갑상선 초음파 | thyroid ultrasound, 갑상선 초음파검사, 경부 초음파, 갑상선 미세침흡인검사, FNA | 내분비외과 |
| 유방 초음파 | breast ultrasound, 유방촬영술, mammography, 유방 검진, 맘모그래피 | 유방외과 |
| 복부 초음파 | abdominal ultrasound, 복부 CT, abdominal CT, 복부 전산화단층촬영 |  |
| 장루 | 인공항문, stoma, ostomy, 결장루, colostomy, 회장루, ileostomy, 장루 조성술, 장루 복원술 | 대장항문외과 |
| 탈장 수술 | 탈장 교정술, herniorrhaphy, hernioplasty, 복강경 탈장수술, TEP, TAPP, 메쉬 삽입 | 탈장외과 |
| 소아 탈장 | 소아 서혜부 탈장, pediatric inguinal hernia, 음낭수종, hydrocele, 잠복고환, undescended testis, 포경수술, circumcision | 소아외과 |
| 부신 종양 | 부신종양, adrenal tumor, 부신 절제술, adrenalectomy, 갈색세포종, pheochromocytoma, 부신 선종, adrenal adenoma | 내분비외과 |
| 임파선 | 림프절, lymph node, 림프절 종대, lymphadenopathy, 림프절 절제 생검, lymph node biopsy, 경부 림프절 |  |
| 쓸개염 | 담낭염, cholecystitis, 급성 담낭염, acute cholecystitis, 담관염, cholangitis | 간담췌외과 |
| 직장탈출 | 직장탈, rectal prolapse, 직장 고정술, rectopexy, 직장점막탈 | 대장항문외과 |
| 모소낭 | 모소동, pilonidal sinus, pilonidal cyst, 천미부 농양, 모소낭 절제술 | 대장항문외과 |
| 장중첩증 | intussusception, 소아 장중첩증, 공기 정복술, air reduction, 소아 복통 | 소아외과 |

## 진료과: 신경과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 두통 | headache, 긴장형 두통, tension-type headache, 두통클리닉, 만성 두통, 두개내압 | 두통 |
| 편두통 | migraine, 전조 편두통, migraine with aura, 박동성 두통, 트립탄, triptan, 보툴리눔 독소 주사 | 두통 |
| 군발두통 | cluster headache, 군발성 두통, 삼차자율신경두통, TAC | 두통 |
| 어지럼증 | dizziness, vertigo, 현훈, 전정신경염, vestibular neuritis, 균형장애 | 어지럼증·전정 |
| 이석증 | benign paroxysmal positional vertigo, BPPV, 양성돌발성두위현훈, 이석정복술, Epley maneuver, 체위변환검사 | 어지럼증·전정 |
| 메니에르병 | Meniere's disease, 메니에르, 내림프수종, endolymphatic hydrops, 이명, tinnitus | 어지럼증·전정 |
| 뇌졸중 | stroke, cerebrovascular accident, CVA, 뇌혈관질환, 편마비, hemiplegia, 혈전용해술 | 뇌혈관질환 |
| 뇌경색 | cerebral infarction, ischemic stroke, 허혈성 뇌졸중, 동맥경화, 혈전, thrombus, tPA | 뇌혈관질환 |
| 뇌출혈 | intracerebral hemorrhage, ICH, hemorrhagic stroke, 출혈성 뇌졸중, 지주막하출혈, subarachnoid hemorrhage | 뇌혈관질환 |
| 일과성 허혈발작 | transient ischemic attack, TIA, 미니 뇌졸중, 일과성 뇌허혈 | 뇌혈관질환 |
| 치매 | dementia, 인지장애, cognitive impairment, 경도인지장애, mild cognitive impairment, MCI, 신경인지검사 | 치매·인지 |
| 알츠하이머 | Alzheimer's disease, AD, 알츠하이머병, 베타아밀로이드, amyloid beta, 아세틸콜린분해효소 억제제 | 치매·인지 |
| 혈관성 치매 | vascular dementia, VaD, 다발경색치매, multi-infarct dementia | 치매·인지 |
| 파킨슨병 | Parkinson's disease, PD, 안정시 떨림, resting tremor, 서동증, bradykinesia, 강직, rigidity, 도파민, 레보도파, levodopa | 이상운동 |
| 수전증 | essential tremor, ET, 본태성 떨림, 본태성진전, action tremor, 자세떨림 | 이상운동 |
| 이상운동 | movement disorder, 근긴장이상, dystonia, 무도병, chorea, 헌팅턴병, Huntington's disease | 이상운동 |
| 안면경련 | hemifacial spasm, 반측 안면경련, 편측안면연축, 안면연축, 보툴리눔 독소, botulinum toxin | 뇌신경질환 |
| 안면마비 | facial palsy, Bell's palsy, 벨마비, 구안와사, 안면신경마비, facial nerve palsy | 뇌신경질환 |
| 삼차신경통 | trigeminal neuralgia, TN, 삼차신경, trigeminal nerve, 안면통증, 카바마제핀, carbamazepine | 뇌신경질환 |
| 뇌전증 | epilepsy, seizure, 간질, 발작, 경련, convulsion, 항경련제, antiepileptic drug, 뇌파검사 | 뇌전증·발작 |
| 경련 | seizure, convulsion, 발작, 전신발작, generalized seizure, 부분발작, focal seizure | 뇌전증·발작 |
| 실신 | syncope, 기절, 졸도, 혈관미주신경성 실신, vasovagal syncope, 기립경사검사, tilt table test | 자율신경 |
| 손발저림 | numbness, paresthesia, 감각이상, 저림증, tingling, 이상감각 | 말초신경 |
| 말초신경병증 | peripheral neuropathy, polyneuropathy, 다발신경병증, 당뇨병성 신경병증, diabetic neuropathy, 신경전도검사 | 말초신경 |
| 손목터널증후군 | carpal tunnel syndrome, CTS, 수근관증후군, 정중신경, median nerve, 신경포착 | 말초신경 |
| 좌골신경통 | sciatica, sciatic neuralgia, 좌골신경, sciatic nerve, 방사통, radiculopathy | 말초신경 |
| 다리저림 | leg numbness, paresthesia, 신경뿌리병증, radiculopathy, 감각저하 | 말초신경 |
| 근무력증 | myasthenia gravis, MG, 중증근무력증, 신경근접합부질환, neuromuscular junction disorder, 안검하수, ptosis | 신경근육질환 |
| 근육병 | myopathy, 근디스트로피, muscular dystrophy, 근위약, muscle weakness, 근전도검사 | 신경근육질환 |
| 루게릭병 | amyotrophic lateral sclerosis, ALS, 근위축성측삭경화증, 운동신경원질환, motor neuron disease, MND | 신경근육질환 |
| 다발성경화증 | multiple sclerosis, MS, 탈수초질환, demyelinating disease, 중추신경계 탈수초 | 탈수초·자가면역 |
| 길랑바레증후군 | Guillain-Barre syndrome, GBS, 급성 염증성 탈수초성 다발신경병증, AIDP, 상행성 마비 | 탈수초·자가면역 |
| 뇌염 | encephalitis, 자가면역뇌염, autoimmune encephalitis, 변연계뇌염, limbic encephalitis | 감염·염증 |
| 뇌수막염 | meningitis, 수막염, 뇌척수액검사, cerebrospinal fluid, lumbar puncture | 감염·염증 |
| 하지불안증후군 | restless legs syndrome, RLS, 하지불안, 다리 이상감각, 도파민 작용제 | 수면장애 |
| 기면증 | narcolepsy, 주간졸림, 탈력발작, cataplexy, 수면마비, sleep paralysis, 수면다원검사, polysomnography | 수면장애 |
| 수면장애 | sleep disorder, 불면증, insomnia, 렘수면행동장애, REM sleep behavior disorder, 수면다원검사 | 수면장애 |
| 수면무호흡 | sleep apnea, 폐쇄성 수면무호흡, obstructive sleep apnea, OSA, 코골이, 수면다원검사 | 수면장애 |
| 뇌파검사 | electroencephalography, EEG, 뇌파, 뇌전기활동, 이상파 | 검사 |
| 근전도검사 | electromyography, EMG, 침근전도, needle EMG, 근육 전기활동 | 검사 |
| 신경전도검사 | nerve conduction study, NCS, nerve conduction velocity, NCV, 신경전도속도, 말초신경 검사 | 검사 |
| 유발전위검사 | evoked potential, EP, 체성감각유발전위, SSEP, 시각유발전위, VEP, 청각유발전위, BAEP | 검사 |
| 뇌MRI | brain MRI, 자기공명영상, magnetic resonance imaging, 뇌자기공명혈관조영, MRA, 확산강조영상, DWI | 검사 |
| 경동맥초음파 | carotid ultrasound, carotid doppler, 경동맥 도플러, 내중막두께, intima-media thickness, 경두개도플러, TCD | 검사 |
| 인지기능검사 | neuropsychological test, 신경심리검사, MMSE, 간이정신상태검사, SNSB, 치매선별검사 | 검사 |
| 기억력 저하 | memory impairment, 건망증, amnesia, 기억장애, 인지저하 | 치매·인지 |
| 보행장애 | gait disturbance, gait disorder, 걸음 이상, 균형장애, 운동실조, ataxia | 이상운동 |
| 근막통증 | myofascial pain, 근육통, 근긴장, 신경병증성 통증, neuropathic pain | 통증 |
| 대상포진 신경통 | postherpetic neuralgia, PHN, 포진후신경통, 신경통, neuralgia, 프레가발린, pregabalin | 통증 |
| 틱 | tic disorder, 투렛증후군, Tourette syndrome, 운동틱, 음성틱 | 이상운동 |

## 진료과: 정신건강의학과

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 우울증 | 우울장애, 주요우울장애, Major Depressive Disorder, MDD, depressive disorder, major depression, 우울감 | 기분장애 |
| 우울감 | 지속성 우울장애, 기분저하증, dysthymia, persistent depressive disorder, 흥미 상실, 무쾌감증, anhedonia | 기분장애 |
| 조울증 | 양극성장애, 양극성 정동장애, bipolar disorder, 조증, 경조증, mania, hypomania, bipolar I, bipolar II | 기분장애 |
| 불안 | 불안장애, 범불안장애, Generalized Anxiety Disorder, GAD, anxiety disorder, 불안증, 과도한 걱정 | 불안장애 |
| 공황장애 | 공황발작, panic disorder, panic attack, 발작성 불안, 심계항진, 과호흡 | 불안장애 |
| 공포증 | 특정공포증, 사회공포증, 사회불안장애, social anxiety disorder, specific phobia, 광장공포증, agoraphobia, 대인공포 | 불안장애 |
| 강박증 | 강박장애, Obsessive-Compulsive Disorder, OCD, 강박사고, 강박행동, obsession, compulsion | 강박관련장애 |
| 불면증 | 불면장애, insomnia, 수면장애, sleep disorder, 입면장애, 수면유지장애, 수면위생 | 수면장애 |
| 수면장애 | 수면무호흡증, sleep apnea, 기면증, narcolepsy, 하지불안증후군, restless legs syndrome, 과다수면, hypersomnia | 수면장애 |
| 조현병 | 정신분열병, schizophrenia, 망상, 환청, 환각, hallucination, delusion, 와해된 사고 | 정신증 |
| 망상 | 망상장애, delusional disorder, 피해망상, persecutory delusion, 과대망상, 정신병적 증상, psychosis | 정신증 |
| 환청 | 환각, auditory hallucination, hallucination, 지각이상, 정신증 증상 | 정신증 |
| ADHD | 주의력결핍 과잉행동장애, Attention-Deficit/Hyperactivity Disorder, 주의력결핍장애, 과잉행동, 충동성, inattention, hyperactivity | 소아청소년정신 |
| 틱장애 | 뚜렛증후군, Tourette syndrome, tic disorder, 운동틱, 음성틱, motor tic, vocal tic | 소아청소년정신 |
| 자폐 | 자폐스펙트럼장애, Autism Spectrum Disorder, ASD, 발달장애, 사회적 의사소통장애, 아스퍼거 | 소아청소년정신 |
| 발달지연 | 발달장애, developmental delay, 지적장애, intellectual disability, 학습장애, learning disorder, 언어발달지연 | 소아청소년정신 |
| 분리불안 | 분리불안장애, separation anxiety disorder, 소아불안, 선택적 함구증, selective mutism | 소아청소년정신 |
| 트라우마 | 외상후 스트레스장애, PTSD, Post-Traumatic Stress Disorder, 급성 스트레스장애, acute stress disorder, 재경험, 플래시백, trauma | 외상스트레스 |
| 적응장애 | adjustment disorder, 스트레스 반응, 스트레스 관련 장애, stress-related disorder | 외상스트레스 |
| 화병 | 분노조절장애, 간헐적 폭발장애, intermittent explosive disorder, 신체화, somatization | 스트레스관련 |
| 치매 | 알츠하이머병, Alzheimer's disease, dementia, 신경인지장애, neurocognitive disorder, 인지장애, 경도인지장애, mild cognitive impairment, MCI | 노인정신 |
| 건망증 | 기억력저하, memory impairment, 인지기능저하, cognitive decline, 경도인지장애, MCI | 노인정신 |
| 섬망 | delirium, 의식혼탁, 급성 혼란상태, 진전섬망, delirium tremens, DT | 노인정신 |
| 노인우울 | 노년기 우울, geriatric depression, 노인성 우울증, late-life depression | 노인정신 |
| 알코올중독 | 알코올사용장애, alcohol use disorder, AUD, 알코올 의존, alcohol dependence, 금단증상, withdrawal, 베르니케-코르사코프 증후군, Wernicke-Korsakoff syndrome | 중독 |
| 중독 | 물질사용장애, substance use disorder, 니코틴의존, nicotine dependence, 약물중독, substance dependence | 중독 |
| 게임중독 | 인터넷게임장애, internet gaming disorder, 스마트폰 과의존, 행위중독, behavioral addiction | 중독 |
| 도박중독 | 도박장애, gambling disorder, 병적 도박, pathological gambling, 충동조절장애 | 중독 |
| 거식증 | 신경성 식욕부진증, anorexia nervosa, 섭식장애, eating disorder, 식이장애 | 섭식장애 |
| 폭식증 | 신경성 폭식증, bulimia nervosa, 폭식장애, binge eating disorder, 섭식장애 | 섭식장애 |
| 산후우울증 | 산후우울, postpartum depression, 주산기 우울, perinatal depression, 산후정신병 | 기분장애 |
| 갱년기우울 | 폐경기 우울, menopausal depression, 갱년기 정신증상 | 기분장애 |
| 성격장애 | 인격장애, personality disorder, 경계성 인격장애, borderline personality disorder, BPD | 성격장애 |
| 신체화 | 신체증상장애, somatic symptom disorder, 건강염려증, 질병불안장애, illness anxiety disorder, hypochondriasis | 신체증상장애 |
| 해리장애 | dissociative disorder, 해리성 기억상실, dissociative amnesia, 이인증, depersonalization | 해리장애 |
| 자살 | 자살사고, suicidal ideation, 자해, self-harm, 위기개입, crisis intervention | 위기개입 |
| 번아웃 | 소진증후군, burnout syndrome, 만성피로, 직무스트레스, occupational stress | 스트레스관련 |
| 인지행동치료 | CBT, Cognitive Behavioral Therapy, 정신치료, psychotherapy, 상담치료, 행동치료, 노출치료, exposure therapy | 정신치료 |
| 심리상담 | 정신치료, 상담치료, counseling, psychotherapy, 면담치료, 지지정신치료, supportive psychotherapy | 정신치료 |
| TMS | 경두개자기자극술, Transcranial Magnetic Stimulation, rTMS, 뇌자극치료, 비침습적 뇌자극 | 뇌자극치료 |
| 전기경련치료 | ECT, Electroconvulsive Therapy, 전기충격치료, 전기자극치료 | 뇌자극치료 |
| 심리검사 | psychological testing, 종합심리검사, Full Battery, 지능검사, Wechsler, 웩슬러, MMPI, 로르샤흐, Rorschach, 투사검사 | 심리평가 |
| 우울증검사 | 벡우울척도, Beck Depression Inventory, BDI, PHQ-9, 우울척도, 해밀턴 우울척도, HAM-D | 심리평가 |
| 수면다원검사 | polysomnography, PSG, 뇌파검사, EEG, 수면검사, 산소포화도, 호흡측정 | 수면평가 |
| 치매검사 | 인지기능검사, MMSE, 간이정신상태검사, CERAD, 신경인지검사, neurocognitive test, SNSB | 노인정신 |
| ADHD검사 | 주의력검사, CAT, Comprehensive Attention Test, 연속수행검사, CPT, Continuous Performance Test | 소아청소년정신 |
| 약물치료 | 항우울제, antidepressant, SSRI, 항불안제, anxiolytic, 항정신병약물, antipsychotic, 기분조절제, mood stabilizer | 약물치료 |
| 스트레스 | 스트레스 관리, stress management, 자율신경검사, HRV, 심박변이도, 바이오피드백, biofeedback | 스트레스관련 |
| 감정조절 | 감정조절장애, 정서불안, 감정기복, mood instability, 변증법적 행동치료, DBT | 정신치료 |
| 월경전증후군 | 월경전불쾌장애, Premenstrual Dysphoric Disorder, PMDD, PMS, 월경전 정신증상 | 기분장애 |

## 진료과: 한의원

| 일반어 | 동의어 (학명·전문용어·영문·치료) | 주력분야 |
|---|---|---|
| 허리 디스크 | 요추 추간판 탈출증, HIVD, lumbar disc herniation, 요통, 추나요법, 침치료, 약침 | 척추·통증 |
| 목 디스크 | 경추 추간판 탈출증, cervical disc herniation, 경추통, 항강증, 추나요법, 경추 교정 | 척추·통증 |
| 척추관 협착증 | 요추관 협착증, spinal stenosis, 요추 협착, 추나요법, 약침치료 | 척추·통증 |
| 척추측만증 | 척추 측만, scoliosis, 체형교정 추나, 측만 교정 | 척추·통증 |
| 거북목 | 일자목, 거북목증후군, forward head posture, 경추 후만, 경추 교정 추나 | 척추·통증 |
| 오십견 | 유착성 관절낭염, 동결견, frozen shoulder, adhesive capsulitis, 견비통, 침치료 | 근골격·통증 |
| 무릎 관절염 | 퇴행성 관절염, 슬관절염, 골관절염, osteoarthritis, 슬통, 약침치료, 봉침 | 근골격·통증 |
| 발목 삐끗 | 발목 염좌, 족관절 염좌, ankle sprain, 근염좌, 침치료, 부항 | 근골격·통증 |
| 손목터널증후군 | 수근관 증후군, carpal tunnel syndrome, 정중신경 압박, 침치료, 약침 | 근골격·통증 |
| 테니스엘보 | 외측 상과염, 주관절통, lateral epicondylitis, 팔꿈치 통증, 약침치료 | 근골격·통증 |
| 교통사고 후유증 | 편타성 손상, whiplash injury, 경항통, 자동차보험 한방치료, 추나요법, 한약 | 척추·통증 |
| 근육통 | 근막통증증후군, myofascial pain syndrome, 담 결림, 근긴장, 부항치료, 침치료 | 근골격·통증 |
| 좌골신경통 | sciatica, 하지 방사통, 요각통, 침치료, 약침 | 척추·통증 |
| 구안와사 | 안면마비, 구안와사 口眼喎斜, facial palsy, Bell's palsy, 말초성 안면신경마비, 침구치료 | 안면·신경 |
| 중풍 | 뇌졸중, 중풍 中風, stroke, 뇌경색, 뇌졸중 후유증, 반신불수, 편마비 재활 | 안면·신경 |
| 두통 | 편두통, 긴장성 두통, migraine, tension headache, 두풍, 침치료, 한약 | 안면·신경 |
| 어지럼증 | 현훈, 현훈 眩暈, vertigo, dizziness, 이석증, BPPV, 침치료, 한약 | 안면·신경 |
| 이명 | 귀울림, 이명 耳鳴, tinnitus, 돌발성 난청, 침치료, 약침, 한약 | 안면·신경 |
| 안면경련 | 눈떨림, 안면 연축, hemifacial spasm, 안검경련, 침치료 | 안면·신경 |
| 불면증 | 수면장애, 불면 不眠, insomnia, 입면장애, 침치료, 한약, 공진단 | 내과·정신 |
| 화병 | 화병 火病, hwabyung, 울화병, 스트레스성 질환, 가슴 답답함, 침치료, 한약 | 내과·정신 |
| 만성피로 | 만성피로증후군, chronic fatigue syndrome, 기허, 공진단, 경옥고, 보약, 한약 | 내과·정신 |
| 소화불량 | 기능성 소화불량, 식체, dyspepsia, 위장장애, 비위허약, 침치료, 한약 | 내과 |
| 과민성대장증후군 | 과민성 장증후군, IBS, irritable bowel syndrome, 설사, 복통, 한약, 침치료 | 내과 |
| 역류성식도염 | 위식도역류, GERD, gastroesophageal reflux, 속쓰림, 담적, 한약치료 | 내과 |
| 변비 | 변비 便秘, constipation, 배변장애, 장기능 저하, 한약, 침치료 | 내과 |
| 감기 | 상기도감염, 감모 感冒, common cold, 몸살, 한약, 쌍화탕 | 내과 |
| 알레르기 비염 | 알레르기성 비염, allergic rhinitis, 비후성 비염, 코막힘, 침치료, 한약, 약침 | 호흡기·면역 |
| 천식 | 기관지 천식, asthma, 호흡곤란, 해수, 한약치료, 침치료 | 호흡기·면역 |
| 만성기침 | 만성 해수, chronic cough, 해수 咳嗽, 기관지염, 한약치료 | 호흡기·면역 |
| 아토피 | 아토피 피부염, atopic dermatitis, 태열, 소양증, 한약치료, 약침 | 피부·면역 |
| 두드러기 | 담마진, urticaria, 피부 발진, 소양증, 한약치료, 침치료 | 피부·면역 |
| 여드름 | 좌창, acne, 면포, 피부 한방치료, 한약, 침치료 | 피부 |
| 월경통 | 생리통, 월경통 月經痛, dysmenorrhea, 월경불순, 뜸치료, 한약, 침치료 | 한방부인과 |
| 월경불순 | 월경부조, 생리불순, menstrual irregularity, 무월경, 한약, 침치료 | 한방부인과 |
| 갱년기 | 갱년기 장애, 폐경기 증후군, menopause, menopausal syndrome, 상열감, 한약치료 | 한방부인과 |
| 난임 | 불임, 난임 難姙, infertility, subfertility, 배란장애, 한약, 뜸치료, 침치료 | 한방부인과 |
| 산후조리 | 산후풍, 산후 회복, postpartum care, 산후 보약, 한약치료 | 한방부인과 |
| 수족냉증 | 수족냉증 手足冷症, cold hands and feet, 말초혈액순환장애, 혈허, 뜸치료, 한약 | 한방부인과 |
| 다이어트 한약 | 비만, obesity, 체중 감량, 한방 비만치료, 감비환, 침치료, 약침 | 비만·체형 |
| 부종 | 수독, edema, 붓기, 림프 순환, 한약치료, 침치료 | 비만·체형 |
| 키 크는 한약 | 성장클리닉, 성장부진, short stature, 성조숙증, 성장치료, 성장 침치료, 한약 | 소아·성장 |
| 성조숙증 | precocious puberty, 2차 성징 조기, 성장 한약치료 | 소아·성장 |
| 틱장애 | 틱, tic disorder, 운동틱, 음성틱, 소아 한방치료, 침치료, 한약 | 소아·성장 |
| 야뇨증 | 야뇨, nocturnal enuresis, 소아 야뇨, 한약치료 | 소아·성장 |
| 식욕부진 | 소아 식욕부진, 비위허약, poor appetite, 입맛없음, 한약치료 | 소아·성장 |
| 보약 | 보약 補藥, tonic herbal medicine, 공진단, 경옥고, 십전대보탕, 녹용 한약 | 한약·체질 |
| 체질 검사 | 사상체질, 사상체질 四象體質, Sasang constitution, 체질 진단, 변증, 한방 진단 | 한약·체질 |
| 침 | 침치료, acupuncture, 호침, 전침, electroacupuncture, 경혈 자극 | 치료법 |
| 뜸 | 뜸치료, 구법, moxibustion, 온구, 애구, 경혈 온열자극 | 치료법 |
| 부항 | 부항치료, 건부항, 습부항, cupping therapy, 사혈요법, 어혈 제거 | 치료법 |
| 추나 | 추나요법, 추나 推拿, chuna manual therapy, 수기요법, 척추 교정, 관절 교정 | 치료법 |
| 약침 | 약침치료, 약침 藥針, pharmacopuncture, 봉침, 봉약침, bee venom acupuncture | 치료법 |
| 한방물리치료 | 한방물리요법, 경근중주파, 경피경근온열, 한방 물리치료기, 경혈 자극치료 | 치료법 |
| 매선 | 매선요법, 매선침, thread embedding, 미용 한방치료, 경혈 매선 | 치료법 |

