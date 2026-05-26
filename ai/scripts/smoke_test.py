"""ai/scripts/smoke_test.py — AI 모듈 실연동 스모크 테스트.

AWS 자격증명이 설정된 상태에서 실제 Bedrock을 호출해 AI 핵심 함수가
end-to-end로 동작하는지 확인한다.

실행:
    python ai/scripts/smoke_test.py

사전 조건:
    1. 개인 계정 자격증명 설정 (aws configure 기본 프로파일 또는 AWS_PROFILE)
       — Bedrock·S3 Vectors·Textract 는 개인 계정에서 운영
    2. ap-northeast-2 리전(서울)에서 아래 모델 액세스 활성화 (Bedrock 콘솔)
       - global.anthropic.claude-sonnet-4-6  (Global cross-region inference profile)
       - amazon.titan-embed-text-v2:0       (임베딩은 지원 계정 us-east-1)

검증 대상:
    1. embed_text             — Titan Embed v2 (가장 저렴, 연결 확인용)
    2. classify_hospital      — Claude Sonnet 4.6 (4 시그널 분류)
    3. generate_description   — Claude Sonnet 4.6 (의료법 5규칙, 프롬프트 경로·치환 버그 수정 검증)

KB 적재·검색(ingest_hospital / retrieve_hospital)은 강사 권한 수령 후 별도 검증.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Windows 콘솔(cp949)에서 한국어가 깨지지 않도록 UTF-8로 재설정
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001 — 재설정 불가 환경은 그대로 진행
    pass

# 레포 루트를 sys.path 에 추가 — `import ai`, `from shared...` 가능하게
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))


def _load_env() -> None:
    """레포 루트의 .env 가 있으면 환경변수로 로드 (이미 설정된 값은 유지)."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


def _build_sample_crawl_data():
    """샘플 병원 크롤링 데이터 — shared/models 의 PublicData 스키마에 맞춰 인라인 구성."""
    from shared.models import CrawlData, CrawledPage, PublicData

    return CrawlData(
        hospital_id="h_smoke_001",
        website_url="https://example-derma.kr",
        pages=[
            CrawledPage(
                url="https://example-derma.kr",
                page_type="main",
                html_text=(
                    "○○피부과 아토피 여드름 습진 진료 안내. "
                    "일반 피부질환 중심의 동네 피부과입니다. "
                    "아토피 치료 여드름 치료 습진 치료 피부 상담"
                ),
                fetched_at=datetime(2026, 5, 1, 9, 0, 0),
            ),
            CrawledPage(
                url="https://example-derma.kr/about",
                page_type="about",
                html_text=(
                    "원장 인사말. 저희 ○○피부과는 2010년 개원 이래 "
                    "일반 피부질환 진료에 집중하며 아토피·여드름·습진 등 "
                    "만성 피부질환 관리를 해 왔습니다."
                ),
                fetched_at=datetime(2026, 5, 1, 9, 0, 5),
            ),
        ],
        images=[],  # use_vision=False 이므로 비움 (S3 접근 불필요)
        public_data=PublicData(
            license_number="h_smoke_001",
            specialists=["피부과전문의"],
            registered_devices=["냉동치료기", "더모스코프"],
        ),
    )


def _build_sample_meta():
    """샘플 병원 기본 정보."""
    from shared.models import Contact, HospitalMeta, Location

    return HospitalMeta(
        hospital_id="h_smoke_001",
        name="○○피부과",
        location=Location(
            address="서울특별시 성북구 동소문로 123",
            lat=37.5894,
            lng=127.0167,
            sido="서울특별시",
            sigungu="성북구",
        ),
        contact=Contact(phone="02-1234-5678", website_url="https://example-derma.kr"),
    )


# 결과 집계: (단계명, 성공 여부, 오류 메시지)
_results: list[tuple[str, bool, str]] = []


def _step(name: str, fn):
    """한 검증 단계를 실행하고 PASS/FAIL을 기록한다."""
    print(f"\n▶ {name} ...")
    try:
        out = fn()
        _results.append((name, True, ""))
        print("  ✅ PASS")
        return out
    except Exception as exc:  # noqa: BLE001 — 스모크 테스트는 모든 예외를 잡아 리포트
        _results.append((name, False, f"{type(exc).__name__}: {exc}"))
        print(f"  ❌ FAIL — {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return None


def main() -> int:
    _load_env()

    print("=" * 64)
    print("AI 모듈 실연동 스모크 테스트")
    print("=" * 64)
    print(f"AWS_REGION             = {os.getenv('AWS_REGION', '(미설정 — us-east-1 권장)')}")
    print(f"BEDROCK_LLM_MODEL_ID   = {os.getenv('BEDROCK_LLM_MODEL_ID', '(기본값 사용)')}")
    print(f"BEDROCK_EMBED_MODEL_ID = {os.getenv('BEDROCK_EMBED_MODEL_ID', '(기본값 사용)')}")

    # 1. embed_text — Titan Embed v2
    def _t_embed():
        import ai

        vec = ai.embed_text("아토피 잘 보는 성북구 피부과")
        assert len(vec) == 1024, f"벡터 차원이 1024가 아님: {len(vec)}"
        print(f"  → 1024차원 벡터 반환 (앞 3개: {[round(x, 4) for x in vec[:3]]})")
        return vec

    _step("embed_text (Titan Embed v2)", _t_embed)

    # 2. classify_hospital — Claude Sonnet 4.6
    crawl = _build_sample_crawl_data()

    def _t_classify():
        import ai

        c = ai.classify_hospital(crawl, use_vision=False)
        print(
            f"  → 표준 진료과목={c.standard_specialty} / "
            f"주력={c.primary_focus} / "
            f"신뢰도={c.confidence.score}({c.confidence.level})"
        )
        return c

    classification = _step("classify_hospital (Claude Sonnet 4.6)", _t_classify)

    # 3. generate_description — 프롬프트 경로·치환 버그 수정 검증 포함
    if classification is not None:

        def _t_describe():
            import ai

            desc = ai.generate_description(
                classification=classification,
                detailed_signals=classification.detailed_signals,
                hospital_meta=_build_sample_meta(),
            )
            print(f"  → headline: {desc.headline}")
            print(f"  → 단락 {len(desc.paragraphs)}개 / 요약: {desc.one_line_summary}")
            return desc

        _step("generate_description (의료법 5규칙)", _t_describe)
    else:
        _results.append(
            ("generate_description (의료법 5규칙)", False, "classify_hospital 실패로 건너뜀")
        )
        print("\n▶ generate_description (의료법 5규칙) ...")
        print("  ⏭  classify_hospital 실패로 건너뜀")

    # 결과 요약
    print("\n" + "=" * 64)
    print("결과 요약")
    print("=" * 64)
    passed = sum(1 for _, ok, _ in _results if ok)
    for name, ok, err in _results:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}" + (f"  — {err}" if err else ""))
    print(f"\n{passed}/{len(_results)} 통과")
    return 0 if passed == len(_results) else 1


if __name__ == "__main__":
    sys.exit(main())
