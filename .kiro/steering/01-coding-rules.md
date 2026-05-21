---
inclusion: always
---

# 코딩 규칙 및 원칙

> 원본: 루트 `CLAUDE.md`

## 언어

**한국어 응답.** UI 카피·로그·주석 모두 한국어가 자연스러우면 한국어. 코드 식별자만 영어.

## 의료법 회색지대 — 주체 명시 원칙 (절대 어기지 말 것)

> **우리는 평가하지 않는다. 병원이 자기 자신을 어떻게 표현했는지를 보여줄 뿐이다.**

| 잘못된 표현 | 적법 표현 |
|---|---|
| "이 병원은 아토피를 잘 본다" | "이 병원이 자기 사이트에서 아토피 진료를 메인으로 표시함" |
| "여기 사마귀 냉동치료기 있음" | "이 병원이 공식 신고한 의료기기 목록에 냉동치료기 포함됨" |
| "이 의사는 탈모 처방을 잘함" | "이 의사가 자기 블로그에서 M자 탈모 처방 사례를 다룸" |

`ai/`의 `generate_description` 프롬프트, `fe/` UI 카피, `be/`의 자동 생성 메시지 전부 이 규칙을 따른다.

## shared/models.py — 단일 진실

BE·AI 한쪽에서 모델 바꾸면 다른 쪽도 동시에 따라간다. 분류 스키마는 M1 시점 동결.

## Git 브랜치 규칙

**main 브랜치에서 직접 코드 작성 금지.** 모든 작업은 feature 브랜치에서 시작.

```bash
git checkout -b feat/<작업명>     # 기능
git checkout -b fix/<버그명>      # 버그
git checkout -b refactor/<영역>   # 리팩터
```

## 커밋 컨벤션

타입은 영어, 제목·본문은 한국어. 스코프로 트랙 명시.

```
feat(ai): generate_description 의료법 5규칙 강제 프롬프트 추가
fix(be): DynamoDB float→Decimal 변환 누락
refactor(shared): ClassificationChange 필드명 명세서 기준으로 통일
```

- 제목 50자 이내, 명령형 어조 ("추가했음" → "추가")
- 본문은 "왜"에 초점. "무엇"은 diff가 말함

## API 응답 포맷

```json
// 성공
{"data": {...}, "meta": {...}}

// 에러
{"error": {"code": "INVALID_PARAMETER", "message": "..."}}
```

## FastAPI OpenAPI → FE TS 타입 자동 생성

`openapi-typescript`로. 수동 동기화 금지.

## 배포

FE: `aws s3 sync` (S3+CloudFront). BE+AI: EC2에 `git pull` 후 프로세스 재시작. CI/CD 없음.
