import json
import os
from typing import Any

from ai.core.aws_clients import get_bedrock_runtime_client

# 텍스트(지원 계정)와 Vision(개인 계정) 클라이언트를 각각 캐시.
_text_client: Any | None = None
_vision_client: Any | None = None


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
    """텍스트 프롬프트를 Bedrock Claude 텍스트 모델에 전송 (지원 계정 Haiku/Nova)."""
    client = get_bedrock_client(use_vision=False)
    model = model_id or os.getenv(
        "BEDROCK_LLM_MODEL_ID",
        "anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = client.invoke_model(modelId=model, body=body)
    return json.loads(response["body"].read())


def invoke_model_with_image(prompt: str, image_b64: str, media_type: str = "image/jpeg") -> dict:
    """이미지 + 텍스트를 Bedrock Vision 모델에 전송 (개인 계정 Sonnet 4.6)."""
    client = get_bedrock_client(use_vision=True)
    model = os.getenv(
        "BEDROCK_VISION_MODEL_ID",
        "global.anthropic.claude-sonnet-4-6",
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    })
    response = client.invoke_model(modelId=model, body=body)
    return json.loads(response["body"].read())
