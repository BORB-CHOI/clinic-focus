// 추천 진료과에 대한 맥락 이유 생성 + 연령 부적합 병원 필터
//
// 우선순위: 계절·날씨 이유 → 키워드(primary_focus) 이유 → 과목 기본 설명
import type { SearchResultItem } from "@/types/domain";

interface WeatherCtx {
  pm25_bucket: string;
  temp_bucket: string;
  temp_diff_bucket: string;
  humidity_bucket: string;
  is_raining: boolean;
}

// ── 키워드 → 맥락 설명 ───────────────────────────────────────────────────────

const KEYWORD_REASON: { kw: string; text: string }[] = [
  // 정형외과
  { kw: "도수치료",   text: "도수치료·물리치료로 근골격계 통증을 직접 교정해요 🤲" },
  { kw: "척추",       text: "디스크·척추 교정을 전문으로 하는 병원이에요 🦴" },
  { kw: "어깨",       text: "어깨 관절 통증·회전근개 부상을 전문으로 봐요 💪" },
  { kw: "무릎",       text: "무릎 관절·인대 부상을 전문으로 치료해요 🦵" },
  { kw: "스포츠",     text: "운동 부상·스포츠 손상을 전문으로 관리해요 🏃" },
  // 피부과
  { kw: "여드름",     text: "여드름·피부 트러블 케어를 전문으로 해요 ✨" },
  { kw: "리프팅",     text: "리프팅·피부 탄력 개선 시술을 중점으로 해요 💆" },
  { kw: "탈모",       text: "탈모 진단·치료를 전문으로 하는 병원이에요 💊" },
  { kw: "아토피",     text: "아토피·민감성 피부 관리를 전문으로 해요 🌿" },
  { kw: "피부암",     text: "피부 종양·피부암 진단을 전문으로 봐요 🔬" },
  { kw: "색소",       text: "기미·잡티·색소 침착 치료를 중점으로 해요" },
  // 내과
  { kw: "심장",       text: "심장 질환·부정맥 관리를 전문으로 봐요 ❤️" },
  { kw: "당뇨",       text: "당뇨 관리·합병증 예방을 전문으로 해요 🩺" },
  { kw: "갑상선",     text: "갑상선 기능 이상을 전문으로 진단·관리해요" },
  { kw: "위내시경",   text: "위·대장 내시경 검사를 중점으로 해요 🔭" },
  { kw: "건강검진",   text: "종합 건강검진·사전 예방 관리를 전문으로 해요 📋" },
  // 이비인후과
  { kw: "비염",       text: "비염·알레르기 비염 치료를 전문으로 해요 🤧" },
  { kw: "코골이",     text: "코골이·수면무호흡증 치료를 전문으로 해요 😴" },
  { kw: "갑상선",     text: "갑상선 수술·이비인후과적 처치를 전문으로 해요" },
  // 한의원
  { kw: "추나",       text: "추나요법·한방 교정으로 체형·통증을 관리해요 🌿" },
  { kw: "침구",       text: "침·뜸을 통한 한방 통증 관리를 전문으로 해요" },
  { kw: "한약",       text: "체질 맞춤 한약 처방을 전문으로 해요 🍃" },
  // 치과
  { kw: "임플란트",   text: "임플란트 시술을 전문으로 하는 병원이에요 🦷" },
  { kw: "교정",       text: "치아 교정을 전문으로 하는 병원이에요 😁" },
  { kw: "심미보철",   text: "심미 보철·라미네이트 시술을 전문으로 해요" },
];

function getKeywordReason(topFocus: string[]): string | null {
  for (const focus of topFocus) {
    for (const { kw, text } of KEYWORD_REASON) {
      if (focus.includes(kw)) return text;
    }
  }
  return null;
}

// ── 과목 기본 설명 (fallback) ────────────────────────────────────────────────

const SPECIALTY_FALLBACK: Record<string, string> = {
  "내과":           "감기·소화기·혈압·혈당 등 다양한 내과 질환을 봐요",
  "정형외과":       "근골격계 통증, 관절·디스크, 도수치료를 전문으로 해요 🦴",
  "피부과":         "피부 트러블, 여드름, 피부 건강을 전문으로 봐요",
  "이비인후과":     "비염, 편도염, 중이염 등 코·귀·목 증상을 전문으로 봐요",
  "안과":           "시력 교정, 라식·라섹, 망막·백내장을 전문으로 봐요",
  "소아청소년과":   "소아·청소년 성장·질환·예방접종을 전문으로 봐요 👶",
  "가정의학과":     "전반적인 건강 관리, 만성질환 예방을 전문으로 봐요",
  "산부인과":       "여성 건강, 산전·산후 관리를 전문으로 봐요",
  "비뇨의학과":     "비뇨기 질환, 남성 건강을 전문으로 봐요",
  "정신건강의학과": "스트레스, 불안, 우울증 등 정신 건강을 전문으로 봐요",
  "신경과":         "두통, 어지럼증, 신경 질환을 전문으로 봐요",
  "한의원":         "한방 치료, 추나·침구·한약 처방을 전문으로 해요",
  "치과":           "충치, 임플란트, 교정 등 구강 건강을 전문으로 봐요 🦷",
  "재활의학과":     "재활 치료, 통증 관리, 기능 회복을 전문으로 봐요",
  "성형외과":       "미용·재건 성형, 지방 흡입 등을 전문으로 해요",
  "외과":           "복부·갑상선 등 외과적 수술을 전문으로 봐요",
};

// ── 계절·날씨 이유 ───────────────────────────────────────────────────────────

function getWeatherReason(
  specialty: string,
  season: string | null,
  weather: WeatherCtx | null,
): string | null {
  const pm25Bad = !!weather && ["bad", "very_bad"].includes(weather.pm25_bucket);
  const isRain  = !!weather?.is_raining;
  const isCold  = !!weather && ["cold", "cool"].includes(weather.temp_bucket);
  const isHot   = !!weather && ["hot", "warm"].includes(weather.temp_bucket);
  const bigDiff = !!weather && ["large", "very_large"].includes(weather.temp_diff_bucket);

  if (specialty === "내과" || specialty === "가정의학과") {
    if (isRain)    return "비 오는 날엔 체온이 낮아져 감기·비염으로 내과를 찾는 분들이 늘어요 🌧️";
    if (bigDiff && (season === "fall" || season === "spring"))
                   return "일교차가 커서 면역력이 떨어지기 쉬운 환절기예요. 감기 조심하세요 🤧";
    if (season === "winter" || isCold) return "한파·환절기 감기·독감 시즌이라 내과 방문이 늘고 있어요 🤒";
    if (season === "summer" || isHot)  return "에어컨 냉방 차이로 냉방병·여름 감기가 잦아 내과를 많이 찾아요 🥶";
    if (pm25Bad)                       return "미세먼지가 나빠 기관지·호흡기 때문에 내과를 찾는 분들이 늘었어요 😷";
  }

  if (specialty === "이비인후과") {
    if (pm25Bad)  return "미세먼지가 나빠 비염·인후통으로 이비인후과 방문이 늘었어요 😷";
    if (isRain)   return "비 오는 날엔 비염·중이염 증상이 심해져 이비인후과를 많이 찾아요 ☔";
    if (season === "fall" || season === "winter" || bigDiff)
                  return "환절기 비염·편도염으로 이비인후과를 많이 찾는 시즌이에요 🤧";
    if (season === "spring") return "꽃가루 알레르기로 비염이 심해지는 봄이에요 🌸";
  }

  if (specialty === "피부과") {
    if (pm25Bad)             return "미세먼지가 나빠 피부 트러블이 늘면서 피부과 수요가 올랐어요 😷";
    if (season === "summer" || isHot) return "자외선·땀으로 피부 트러블이 잦은 여름, 피부과를 많이 찾는 시즌이에요 ☀️";
    if (season === "spring") return "건조함·꽃가루로 피부 과민이 심해지는 봄이에요 🌸";
    if (season === "winter") return "건조한 겨울엔 피부 장벽이 약해져 피부과를 찾는 분들이 늘어요 ❄️";
  }

  if (specialty === "정형외과") {
    if (season === "winter" || isCold) return "겨울 한파에 낙상·관절 통증으로 정형외과를 많이 찾는 시즌이에요 🦴";
    if (bigDiff) return "일교차가 크면 관절·근육이 굳기 쉬워 정형외과 방문이 늘어요";
    if (season === "summer" || isHot)  return "여름철 활동량이 늘면서 운동 부상·근육통으로 정형외과를 찾는 분들이 많아요 🏃";
    if (season === "spring" || season === "fall") return "야외 활동이 늘어나는 계절, 근골격계 부상 예방·관리가 중요해요 🌿";
  }

  if (specialty === "안과") {
    if (season === "spring" || pm25Bad) return "봄 꽃가루·미세먼지로 안구 충혈·가려움이 심해지는 시즌이에요 👁️";
    if (season === "summer")            return "강한 자외선으로 눈 건강에 주의가 필요한 시즌이에요 ☀️";
    if (season === "winter")            return "건조한 공기로 안구건조증이 심해지는 시즌이에요 ❄️";
  }

  if (specialty === "소아청소년과") {
    if (isRain || isCold || season === "winter") return "면역이 약한 아이들, 환절기·겨울 감기 예방 관리가 중요해요 🤧";
    if (season === "summer") return "수족구·여름 감기 등 소아 감염 질환이 늘어나는 시즌이에요 🌡️";
  }

  if (specialty === "한의원") {
    if (bigDiff || season === "fall" || season === "spring")
      return "환절기에는 체력 저하·면역 관리를 위해 한의원을 많이 찾아요 🍂";
    if (isCold || season === "winter") return "겨울철 냉증·관절 통증 관리에 한방 치료를 많이 찾아요 🌿";
  }

  return null;
}

// ── 메인 함수 (season/weather → keyword → specialty fallback) ────────────────

export function getContextReason(
  specialty: string,
  season: string | null,
  weather: WeatherCtx | null,
  topFocus?: string[],
): string | null {
  // 1. 계절·날씨 우선
  const weatherReason = getWeatherReason(specialty, season, weather);
  if (weatherReason) return weatherReason;

  // 2. 추천 병원 주요 키워드 기반
  if (topFocus?.length) {
    const kwReason = getKeywordReason(topFocus);
    if (kwReason) return kwReason;
  }

  // 3. 과목 기본 설명 fallback
  return SPECIALTY_FALLBACK[specialty] ?? null;
}

// ── 연령대별 부적합 primary_focus 필터 ──────────────────────────────────────

const OLDER_FOCUSED: string[] = ["순환기", "고혈압", "당뇨", "내분비", "심장", "치매", "뇌졸중", "노인"];
const YOUNG_COHORTS: string[] = ["teens", "20s", "30s"];

// 10대·20대에게 성인 안티에이징 시술 위주 병원은 부적합
const TEEN_ANTIAGING: string[] = ["리프팅", "탄력", "안티에이징", "항노화", "실리프팅", "보톡스", "필러", "주름"];

function isAgeMismatch(hospital: SearchResultItem, ageBucket: string): boolean {
  if (!YOUNG_COHORTS.includes(ageBucket)) return false;
  const focuses = hospital.primary_focus ?? [];
  if (focuses.length === 0) return false;

  // 순환기·당뇨 등 고령성 질환 중심 → 후순위
  if (focuses.every((f) => OLDER_FOCUSED.some((kw) => f.includes(kw)))) return true;

  // 10대에게 성인 안티에이징 전문 병원은 후순위
  if (ageBucket === "teens" && focuses.every((f) => TEEN_ANTIAGING.some((kw) => f.includes(kw)))) {
    return true;
  }

  return false;
}

/**
 * 나이 코호트에 맞지 않는 병원을 뒤로 정렬해 앞 `take`개를 반환.
 * 필터링이 아닌 정렬이라 결과가 0개가 되는 일은 없다.
 */
export function sortHospitalsByAgefit(
  hospitals: SearchResultItem[],
  ageBucket: string | null,
  take = 3,
): SearchResultItem[] {
  if (!ageBucket) return hospitals.slice(0, take);
  const fit   = hospitals.filter((h) => !isAgeMismatch(h, ageBucket));
  const unfit = hospitals.filter((h) =>  isAgeMismatch(h, ageBucket));
  return [...fit, ...unfit].slice(0, take);
}
