import json
import os
from typing import Any

from ai.core.aws_clients import (
    get_bedrock_runtime_client,
    get_bedrock_runtime_client_support,
)

# 텍스트(지원 계정)와 Vision(개인 계정) 클라이언트를 각각 캐시.
_text_client: Any | None = None
_vision_client: Any | None = None
_support_text_client: Any | None = None

# 지원 계정 on-demand 가용 텍스트 모델 기본값. 재랭킹 A/B(강남 84토픽, temp0) 실측에서
# Nova Lite 가 Claude 3 Haiku(P@1 0.762)·Nova Pro(0.774)보다 우위(P@1 0.810)라 기본값.
# (Haiku 4.5·Sonnet·inference profile 은 SafeRole 권한으로 막혀 on-demand Nova/Claude3 만 가능.)
DEFAULT_SUPPORT_TEXT_MODEL = "amazon.nova-lite-v1:0"


def get_bedrock_client(use_vision: bool = False) -> Any:
    global _text_client, _vision_client
    if use_vision:
        if _vision_client is None:
            _vision_client = get_bedrock_runtime_client(use_vision=True)
        return _vision_client
    if _text_client is None:
        _text_client = get_bedrock_runtime_client(use_vision=False)
    return _text_client


def invoke_model(prompt: str, model_id: str | None = None) -> dict:
    """텍스트 프롬프트를 Bedrock Claude 텍스트 모델에 전송 (개인 계정 Haiku, 서울).

    ⚠️ 반드시 **global. inference profile** 형태여야 한다 — 직접 모델 ID
    (`anthropic.claude-haiku-4-5-...`)는 on-demand 호출 미지원(ValidationException).
    """
    client = get_bedrock_client(use_vision=False)
    model = model_id or os.getenv(
        "BEDROCK_LLM_MODEL_ID",
        "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = client.invoke_model(modelId=model, body=body)
    return json.loads(response["body"].read())


def invoke_text_support(
    prompt: str, model_id: str | None = None, max_tokens: int = 1024, temperature: float = 0.0
) -> str:
    """지원 계정(인스턴스 프로파일, us-east-1) 텍스트 모델 호출 → 응답 **텍스트**.

    개인 계정 제거 후 검색 런타임 LLM(재랭커)의 유일 경로. on-demand 가용 모델만
    호출 가능 — 기본 Claude 3 Haiku, ``amazon.nova-*`` 면 Nova 포맷으로 분기.
    Haiku 4.5·Sonnet·``us.``/``global.`` inference profile 은 SafeRole 권한으로 막혀
    ValidationException/AccessDeniedException 이 난다(aws_clients 모듈 docstring 참조).

    ``temperature`` 기본 0.0 — 재랭킹/추출 같은 결정적 채점 태스크는 sampling 을 끄는 게
    정확하고 재현 가능(약한 모델일수록 효과 큼).
    """
    client = _support_text_client_cached()
    model = model_id or os.getenv("RERANK_MODEL_ID", DEFAULT_SUPPORT_TEXT_MODEL)
    if model.startswith("amazon.nova"):
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
        })
        response = client.invoke_model(modelId=model, body=body)
        out = json.loads(response["body"].read())
        return out["output"]["message"]["content"][0]["text"]
    # Anthropic Messages 포맷 (Claude 3 Haiku 등)
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = client.invoke_model(modelId=model, body=body)
    out = json.loads(response["body"].read())
    return "".join(b.get("text", "") for b in out.get("content", []) if b.get("type") == "text")


def _support_text_client_cached() -> Any:
    global _support_text_client
    if _support_text_client is None:
        _support_text_client = get_bedrock_runtime_client_support()
    return _support_text_client


def invoke_model_with_image(prompt: str, image_b64: str, media_type: str = "image/jpeg") -> dict:
    """이미지 1장 + 텍스트를 Bedrock Vision 모델에 전송 (개인 계정 Sonnet 4.6)."""
    return invoke_model_with_images(prompt, [(image_b64, media_type)])


def invoke_model_with_images(prompt: str, images: list[tuple[str, str]]) -> dict:
    """여러 이미지 + 텍스트를 **한 번의** Bedrock Vision 호출로 전송 (멀티이미지 배칭).

    한 병원 페이지의 스크롤 타일들 + 개별 사진을 한 메시지에 모아 1회 호출 →
    이미지당 1콜(순차 ~8초×N) 대비 라운드트립이 1회로 줄어 병원당 수십 초 절감.
    입력 토큰은 이미지 합산이라 비용은 비슷하고 지연만 크게 준다.

    Args:
        prompt: 텍스트 프롬프트(맨 뒤에 배치).
        images: (base64, media_type) 튜플 리스트. 순서대로 content 에 들어간다.
    """
    client = get_bedrock_client(use_vision=True)
    model = os.getenv("BEDROCK_VISION_MODEL_ID", "global.anthropic.claude-sonnet-4-6")
    content: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}}
        for b64, mt in images
    ]
    content.append({"type": "text", "text": prompt})
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        # 여러 이미지를 종합 서술하므로 넉넉히. 모델은 필요한 만큼만 생성한다.
        "max_tokens": 3072,
        "messages": [{"role": "user", "content": content}],
    })
    response = client.invoke_model(modelId=model, body=body)
    return json.loads(response["body"].read())
