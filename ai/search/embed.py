"""
embed.py — Bedrock Titan Embed Text v2 래퍼.

- embed_text(text) -> list[float] : 1024 차원 벡터 반환
- 8192 토큰 초과 시 TextTooLongError
- Bedrock 호출 실패 시 BedrockInvocationError
- 테스트 mockability: @patch("ai.search.embed._get_embed_client") 로 패치 가능
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

import boto3
import botocore.exceptions

from ai.core.exceptions import BedrockInvocationError, TextTooLongError

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

logger = logging.getLogger(__name__)

# Titan Embed Text v2 최대 입력 토큰 제한 (공식 한도)
_MAX_TOKENS = 8192

# 토큰 근사치 — 한국어 평균 2~3 chars/token, 영어는 ~4 chars/token.
# 보수적으로 2 chars/token 으로 계산해 초과 여부를 사전 검증한다.
# 실제 tokenizer 대신 근사치를 쓰는 이유:
#   1) Titan tokenizer 는 SDK 에 노출되지 않음
#   2) 길이 초과 케이스는 명백히 긴 텍스트 (수만 자)라 근사치로도 충분
_CHARS_PER_TOKEN_APPROX = 2

# 벡터 차원 — Titan Embed Text v2 고정값
EMBEDDING_DIM = 1024

_embed_client: "BedrockRuntimeClient | None" = None


def _get_embed_client() -> "BedrockRuntimeClient":
    """boto3 bedrock-runtime 클라이언트 팩토리.

    전역 캐싱으로 Lambda 재사용 시 재생성 비용을 줄인다.
    테스트에서 @patch("ai.embed._get_embed_client") 로 교체 가능.
    """
    global _embed_client
    if _embed_client is None:
        _embed_client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "ap-northeast-2"),
        )
    return _embed_client


def embed_text(text: str) -> list[float]:
    """텍스트를 Titan Embed Text v2 벡터로 변환한다.

    Args:
        text: 임베딩할 텍스트 (빈 문자열 포함 가능)

    Returns:
        1024 차원 float 리스트

    Raises:
        TextTooLongError: 입력이 8192 토큰 근사치를 초과할 때
        BedrockInvocationError: Bedrock API 호출 실패 시
    """
    if not text:
        # 빈 입력 → 0 벡터 반환 (위치 전용 검색의 더미 벡터 생성 경로)
        logger.debug("embed_text: 빈 텍스트 → 영벡터 반환")
        return [0.0] * EMBEDDING_DIM

    # 토큰 초과 사전 검증 (근사치)
    approx_tokens = len(text) // _CHARS_PER_TOKEN_APPROX
    if approx_tokens > _MAX_TOKENS:
        raise TextTooLongError(
            f"입력 텍스트가 너무 깁니다. "
            f"근사 토큰 수 {approx_tokens} > 제한 {_MAX_TOKENS}. "
            f"호출 전에 청킹하세요."
        )

    model_id = os.getenv("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
    payload = json.dumps({"inputText": text})

    try:
        client = _get_embed_client()
        response = client.invoke_model(
            modelId=model_id,
            body=payload,
            accept="application/json",
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
    except botocore.exceptions.ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        logger.error("Bedrock 임베딩 호출 실패 (ClientError): %s", error_code)
        raise BedrockInvocationError(
            f"Bedrock invoke_model 실패 (모델: {model_id}): {error_code}"
        ) from exc
    except Exception as exc:
        logger.error("Bedrock 임베딩 호출 실패 (예외): %s", exc)
        raise BedrockInvocationError(
            f"Bedrock invoke_model 실패 (모델: {model_id}): {exc}"
        ) from exc

    embedding: list[float] = result.get("embedding", [])
    if len(embedding) != EMBEDDING_DIM:
        raise BedrockInvocationError(
            f"반환된 벡터 차원이 예상({EMBEDDING_DIM})과 다릅니다: {len(embedding)}"
        )

    return embedding
