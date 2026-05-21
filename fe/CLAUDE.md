# fe/ — 프론트엔드 트랙 (하재원)

상위 컨텍스트는 `../CLAUDE.md`, API 스펙은 `../docs/API-FE-BE.md`.

## 스택

| 항목 | 선택 |
|---|---|
| 언어 | TypeScript |
| 프레임워크 | React + Vite (Next.js 안 씀 — SEO·SSR 안 함) |
| UI | Tailwind CSS + shadcn/ui |
| 서버 상태 | TanStack Query |
| 라우팅 | React Router |
| API 클라이언트 | fetch (axios 안 씀) |
| 지도 | 카카오맵 JavaScript SDK |
| 빌드·배포 | `vite build` → S3 + CloudFront (`aws s3 sync` 수동) |
| 타입 | BE OpenAPI → `npx openapi-typescript` 자동 생성. 수동 작성 금지 |

## 핵심 화면

1. **검색 결과** — 입력창 + 카드 리스트. 카드는 `one_line_summary` 한 줄 + 신뢰도 배지 + 표준 진료과목 + 실제 주력 태그
2. **병원 상세 페이지 (9개 영역)** ⭐ **데모 핵심 장면** — 영역별 응답 필드 매핑은 `../docs/API-FE-BE.md` "영역별 필드 매핑" 표 참조. 그대로 1:1 매핑
3. **지도 검색** — 카카오맵 임베드, GPS 기반, 반경 슬라이더(0.5/1/3/5/10km), 신뢰도 등급별 마커 색상 (확실=초록 / 추정=노랑 / 정보 부족=회색)

## 상세 페이지 ① 헤드라이너 렌더링 규칙

`ai_description`은 본 서비스의 핵심 차별점이라 렌더링이 중요:

- `headline` — 최상단 큰 글씨
- 각 `paragraphs[].text` 옆 또는 끝에 `citations` 시그널을 배지로 표시 (예: `[사이트]` `[Vision]` `[블로그]` `[후기]`)
- 배지 클릭 시 ④ 영역의 `detailed_signals` 해당 섹션으로 스크롤 또는 모달
- `metadata.warning`이 있으면 페이지 상단 경고 배너
- `metadata.data_completeness < 0.6`이면 빈 영역에 "정보 부족" 표시

## 익명 피드백 디바이스 ID

```typescript
// utils/device.ts
const DEVICE_ID_KEY = 'app_device_id';
export function getDeviceId(): string {
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = 'd_' + crypto.randomUUID();
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
}
```

같은 디바이스에서 같은 병원에 1회만 피드백 가능 (BE에서 `DUPLICATE_FEEDBACK` 409 반환).

## 작업 원칙

- Mock 데이터로 화면 골격 먼저 → 분류 스키마 동결(M1) 후 BE OpenAPI 타입으로 props 교체
- 다크모드·완전한 모바일 반응형은 별도 작업 항목으로 잡지 않음 (바이브 코딩 기본 수준)
- 의료법 카피는 항상 주체 명시 표현 (`../CLAUDE.md` 표 참조)
- 컴포넌트 분리는 9개 영역 단위가 1차 기준 — 영역별 데이터 출처가 다르므로
