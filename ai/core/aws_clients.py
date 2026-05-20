"""
ai/core/aws_clients.py — 계정별 boto3 세션 팩토리.

EC2 환경에서 두 개의 AWS 계정을 다룬다:
  - 지원 계정: EC2 인스턴스 프로파일로 자동 인증 (DynamoDB, S3)
  - 개인 계정: AI_AWS_* 환경변수로 명시적 인증 (Bedrock, S3 Vectors, Textract)

모든 AI 모듈은 이 팩토리를 통해서만 boto3 클라이언트를 만든다.
"""
from __future__ import annotations

import os
from typing import Any

import boto3

# ---------------------------------------------------------------------------
# 개인 계정 세션 (Bedrock · S3 Vectors · Textract)
# ---------------------------------------------------------------------------

_ai_session: boto3.Session | None = None

def _get_ai_session() -> boto3.Session:
    """개인 계정 boto3 세션. AI_AWS_* 환경변수로 자격증명."""
    global _ai_session
    if _ai_session is None:
        access_key = os.environ.get("AI_AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AI_AWS_SECRET_ACCESS_KEY")
        session_token = os.environ.get("AI_AWS_SESSION_TOKEN")  # optional
        profile = os.environ.get("AI_AWS_PROFILE")

        if access_key and secret_key:
            _ai_session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=os.environ.get("AI_AWS_REGION", "us-east-1"),
            )
        elif profile:
            _ai_session = boto3.Session(
                profile_name=profile,
                region_name=os.environ.get("AI_AWS_REGION", "us-east-1"),
            )
        else:
            raise RuntimeError(
                "개인 계정 자격증명이 없습니다. "
                "AI_AWS_ACCESS_KEY_ID + AI_AWS_SECRET_ACCESS_KEY 또는 "
                "AI_AWS_PROFILE 환경변수를 설정하세요."
            )
    return _ai_session


_ai_region: str | None = None

def _ai_region_name() -> str:
    """개인 계정 리전명 캐시. AI_AWS_REGION 환경변수 또는 기본값 'us-east-1'."""
    global _ai_region
    if _ai_region is None:
        _ai_region = os.environ.get("AI_AWS_REGION", "us-east-1")
    return _ai_region


# ---------------------------------------------------------------------------
# 공개 팩토리 함수 — AI 모듈용 (개인 계정)
# ---------------------------------------------------------------------------

def get_bedrock_runtime_client() -> Any:
    """개인 계정 Bedrock Runtime 클라이언트."""
    return _get_ai_session().client("bedrock-runtime", region_name=_ai_region_name())


def get_s3vectors_client() -> Any:
    """개인 계정 S3 Vectors 클라이언트."""
    return _get_ai_session().client("s3vectors", region_name=_ai_region_name())


def get_textract_client() -> Any:
    """개인 계정 Textract 클라이언트."""
    return _get_ai_session().client("textract", region_name=_ai_region_name())


def get_s3_client_for_images() -> Any:
    """개인 계정 S3 클라이언트 — 이미지 다운로드용 (크롤 결과 이미지가 개인 계정 S3에 있을 때)."""
    return _get_ai_session().client("s3", region_name=_ai_region_name())


# ---------------------------------------------------------------------------
# 공개 팩토리 함수 — BE 모듈용 (지원 계정, 인스턴스 프로파일)
# ---------------------------------------------------------------------------

_support_region: str | None = None

def _support_region_name() -> str:
    """지원 계정 리전명 캐시. AWS_REGION 환경변수 또는 기본값 'us-east-1'."""
    global _support_region
    if _support_region is None:
        _support_region = os.environ.get("AWS_REGION", "us-east-1")
    return _support_region


def get_dynamodb_resource() -> Any:
    """지원 계정 DynamoDB resource (인스턴스 프로파일)."""
    return boto3.resource("dynamodb", region_name=_support_region_name())


def get_support_s3_client() -> Any:
    """지원 계정 S3 클라이언트 (크롤 데이터 저장용)."""
    return boto3.client("s3", region_name=_support_region_name())


# ---------------------------------------------------------------------------
# 테스트 지원 — 세션 캐시 초기화
# ---------------------------------------------------------------------------

def _reset_cache() -> None:
    """단위 테스트에서 세션 캐시를 초기화할 때 사용. 프로덕션 코드에서 호출 금지."""
    global _ai_session, _ai_region, _support_region
    _ai_session = None
    _ai_region = None
    _support_region = None
