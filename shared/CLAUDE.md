# shared/ — 공유 Pydantic 모델

**BE와 AI의 단일 진실 (single source of truth).** 양쪽이 같은 EC2 프로세스에서 도므로 같은 `models.py`를 import 해서 쓴다. FE는 BE의 FastAPI OpenAPI 스펙에서 `openapi-typescript`로 TS 타입을 자동 생성하므로 결국 여기가 모든 타입의 출발점.

## 정의해야 할 모델 목록

자세한 필드는 `../docs/API-BE-AI.md` "공유 Pydantic 모델" 섹션 참조. 줄여 보면:

- 크롤링: `CrawlData`, `CrawledPage`, `CrawledImage`, `PublicData`
- 분류: `Classification`, `Confidence`, `SignalContributions`, `DetailedSignals`, `SelfClaimSignal`, `VisionSignal`, `BlogSignal`, `ReviewSignal`
- AI 설명: `HospitalDescription`, `DescriptionParagraph` ⭐
- 검색: `SearchQuery`, `SearchResult`
- 이미지: `ImageAnalysisResult`
- 피드백: `FeedbackEntry`, `FeedbackStats`
- 상세 페이지 영역: `Service`, `ExcludedService`, `Equipment`, `PriceItem`, `Doctor`, `Location`, `OperatingHours`, `Contact`, `RelatedHospital`, `ClassificationChange`, `DataMetadata`

## 변경 규칙

- **M1 시점 분류 스키마 동결.** 이후 변경은 BE·AI·FE 세 트랙 동시 수정 필요. 작은 변경도 전체 영향
- 새 필드 추가는 비교적 안전 (Optional + 기본값). 기존 필드 rename·삭제는 위험
- 모든 모델에 `model_config = ConfigDict(extra="forbid")` 권장. AI 출력 검증 시 위반 빨리 잡힘

## FE 타입 동기화

```bash
# BE 로컬 띄운 상태에서
cd ../fe && npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
```

PR 전 항상 재생성. 수동 작성·수정 금지.
