/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1rem",
      screens: {
        "2xl": "1280px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // ── 신뢰도 등급 (확실 / 추정 / 정보 부족) ───────────────────
        // 모던 SaaS 톤. 톤 C 베이스에서 hue 를 살짝 옮기고 채도·명도 대비를
        // 한 단계 강화해 시각 신호를 분명히 한다.
        //   확실     → 묵직한 그린 (의료 친화·신뢰감)
        //   추정     → 따뜻한 오렌지 (앰버보다 한 톤 빨강 쪽)
        //   정보부족 → 짙은 슬레이트 (배지·텍스트 대비 ↑)
        //
        // 한 hue 당 4단계: 50(배경) / 100(보더) / 500(아이콘·DEFAULT) / 700(텍스트).
        // SVG 마커는 단일색이 필요해 500 사용 — src/lib/kakaoMap.ts 의
        // CONFIDENCE_HEX 와 동기화.
        confidence: {
          high: {
            DEFAULT: "hsl(151 81% 36%)",
            50: "hsl(150 84% 95%)",
            100: "hsl(150 78% 86%)",
            500: "hsl(151 81% 36%)",
            700: "hsl(155 90% 22%)",
          },
          medium: {
            DEFAULT: "hsl(28 92% 48%)",
            50: "hsl(36 100% 95%)",
            100: "hsl(34 96% 86%)",
            500: "hsl(28 92% 48%)",
            700: "hsl(20 90% 35%)",
          },
          low: {
            DEFAULT: "hsl(215 19% 35%)",
            50: "hsl(214 32% 95%)",
            100: "hsl(214 28% 86%)",
            500: "hsl(215 19% 35%)",
            700: "hsl(217 33% 18%)",
          },
        },
        // ── 4 시그널 (citations / 시그널 기여도 분해) ───────────────
        // confidence 와 hue 거리를 멀게 잡아 한 화면(헤드라이너 단락 끝)에
        // 동시에 등장해도 색 충돌 없게 정렬.
        //   self_claim → 짙은 블루   vision  → 짙은 바이올렛
        //   blog       → 따뜻한 레드 reviews → 핑크
        // 라벨은 src/lib/signals.ts SIGNAL_LABEL 과 매핑.
        signal: {
          "self-claim": {
            DEFAULT: "hsl(221 83% 53%)",
            50: "hsl(214 100% 96%)",
            100: "hsl(213 96% 87%)",
            500: "hsl(221 83% 53%)",
            700: "hsl(224 76% 40%)",
          },
          vision: {
            DEFAULT: "hsl(262 83% 58%)",
            50: "hsl(262 100% 97%)",
            100: "hsl(261 95% 90%)",
            500: "hsl(262 83% 58%)",
            700: "hsl(263 70% 42%)",
          },
          blog: {
            DEFAULT: "hsl(15 88% 50%)",
            50: "hsl(20 100% 95%)",
            100: "hsl(18 96% 87%)",
            500: "hsl(15 88% 50%)",
            700: "hsl(10 82% 38%)",
          },
          reviews: {
            DEFAULT: "hsl(330 81% 55%)",
            50: "hsl(327 100% 96%)",
            100: "hsl(326 95% 89%)",
            500: "hsl(330 81% 55%)",
            700: "hsl(335 78% 38%)",
          },
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      // ── 본문 폰트 ────────────────────────────────────────────────
      // Pretendard Variable (static 풀버전) 우선. dynamic-subset 은
      // unicode-range 분기에서 한글 매칭이 빠지는 환경이 있어 PoC 단계엔
      // 풀버전을 사용. CDN 임포트는 index.html 의 <link>, html 의
      // font-family 강제 적용은 src/index.css.
      fontFamily: {
        sans: [
          "Pretendard Variable",
          "Pretendard",
          "-apple-system",
          "BlinkMacSystemFont",
          "system-ui",
          "Roboto",
          "Helvetica Neue",
          '"Segoe UI"',
          '"Apple SD Gothic Neo"',
          '"Noto Sans KR"',
          '"Malgun Gothic"',
          "sans-serif",
        ],
      },
      // 한글 가독성을 위해 자간을 미세하게 좁힘 (본문은 그대로 유지하고
      // 제목·헤드라인 위계에서만 활용 — 페이지별 다듬기 라운드에서 적용)
      letterSpacing: {
        tighter: "-0.02em",
        tight: "-0.01em",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
