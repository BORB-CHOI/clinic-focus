import json
import os
from typing import Any

from ai.core.aws_clients import get_bedrock_runtime_client

_bedrock_client = None


def get_bedrock_client() -> Any:
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = get_bedrock_runtime_client()
    return _bedrock_client


def invoke_model(prompt: str, model_id: str | None = None) -> dict:
    """텍스트 프롬프트를 Bedrock Claude에 전송하고 응답 dict를 반환."""
    client = get_bedrock_client()
    model = model_id or os.getenv(
        "BEDROCK_LLM_MODEL_ID",
        "global.anthropic.claude-sonnet-4-6",
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = client.invoke_model(modelId=model, body=body)
    return json.loads(response["body"].read())


def invoke_model_with_image(prompt: str, image_b64: str, media_type: str = "image/jpeg") -> dict:
    """이미지 + 텍스트를 Bedrock Claude Vision에 전송."""
    client = get_bedrock_client()
    model = os.getenv(
        "BEDROCK_LLM_MODEL_ID",
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
