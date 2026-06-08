"""
ai/core/aws_clients.py — 계정별 boto3 세션 팩토리.

EC2 환경에서 AWS 계정을 다룬다:
  - 지원 계정 (us-east-1, 인스턴스 프로파일): DynamoDB, S3, Bedrock KB, Titan Embed v2,
    그리고 **검색 런타임 텍스트 LLM(재랭커)** — on-demand 가용 모델만
    (Claude 3 Haiku `anthropic.claude-3-haiku-20240307-v1:0` / Nova `amazon.nova-*`).
  - ~~개인 계정 (ap-northeast-2, AI_AWS_*): Bedrock Sonnet 4.6 Vision~~ — **제거됨**.
    개인 계정은 없어진 지 오래(자격증명 데드). 아래 _get_ai_session() 는 레거시(미사용).

★ 지원 계정 Bedrock 제약(SafeRole-kmuproj-10 실측 2026-06-08):
  - on-demand 가능: Claude 3 Haiku, Nova 전 계열(micro/lite/pro). 정상 invoke.
  - **막힘**: Haiku 4.5(on-demand=ValidationException)·Claude 3.5 Haiku·모든
    `us.`/`global.` cross-region inference profile(=AccessDeniedException).
  - 그래서 재랭커 기본 모델은 Claude 3 Haiku(on-demand). Haiku 4.5/Sonnet/프로파일 ❌.

검색 런타임 LLM(재랭커)·KB·DDB·S3 전부 지원 계정. 사전처리 데모였던 generate_description
(Sonnet/Haiku4.5)·Vision(Sonnet)은 개인 계정 의존이라 현재 신규 생성 불가(기존 적재분은
정적이라 무관). 모든 AI 모듈은 이 팩토리를 통해서만 boto3 클라이언트를 만든다.
"""
from __future__ import annotations

import os
from typing import Any

import boto3

# ---------------------------------------------------------------------------
# 개인 계정 세션 (Bedrock LLM/Vision — Sonnet 4.6, 서울 리전)
# ---------------------------------------------------------------------------

_ai_session: boto3.Session | None = None

def _get_ai_session() -> boto3.Session:
    """개인 계정 boto3 세션. AI_AWS_* 환경변수로 자격증명."""
    global _ai_session
    if _ai_session is None:
        access_key = os.environ.get("AI_AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AI_AWS_SECRET_ACCESS_KEY")
        session_token = os.environ.get("AI_AWS_SESSION_TOKEN") or None  # optional
        profile = os.environ.get("AI_AWS_PROFILE")

        # 장기 자격증명(AKIA)엔 세션 토큰이 불필요하고, .env 에 남은 **stale 토큰**을 그대로
        # 넘기면 InvalidSignatureException 으로 호출이 깨진다. AKIA 면 토큰을 무시한다.
        # (임시 자격증명 ASIA 는 토큰 필수 — 그땐 그대로 전달)
        if access_key and access_key.startswith("AKIA"):
            session_token = None

        if access_key and secret_key:
            _ai_session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                region_name=os.environ.get("AI_AWS_REGION", "ap-northeast-2"),
            )
        elif profile:
            _ai_session = boto3.Session(
                profile_name=profile,
                region_name=os.environ.get("AI_AWS_REGION", "ap-northeast-2"),
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
    """개인 계정 리전명 캐시. AI_AWS_REGION 환경변수 또는 기본값 'ap-northeast-2' (서울 — Sonnet 4.6 Global profile 호출용)."""
    global _ai_region
    if _ai_region is None:
        _ai_region = os.environ.get("AI_AWS_REGION", "ap-northeast-2")
    return _ai_region


# ---------------------------------------------------------------------------
# 공개 팩토리 함수 — AI 모듈용 (개인 계정)
# ---------------------------------------------------------------------------

def get_bedrock_runtime_client(use_vision: bool = False) -> Any:
    """⚠️ 레거시(개인 계정) Bedrock Runtime — 개인 계정 제거로 **사실상 데드**.

    generate_description(Sonnet/Haiku4.5)·Vision 이 아직 이 경로를 참조하지만 개인
    계정 자격증명(AI_AWS_*)이 없어져 런타임 호출은 실패한다(기존 적재분은 정적).
    검색 런타임 텍스트 LLM(재랭커)은 get_bedrock_runtime_client_support() 를 쓴다.
    """
    return _get_ai_session().client("bedrock-runtime", region_name=_ai_region_name())


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


def get_bedrock_runtime_client_support() -> Any:
    """지원 계정 Bedrock Runtime (인스턴스 프로파일, us-east-1).

    검색 런타임 텍스트 LLM(재랭커)용. on-demand 가용 모델만 호출 가능
    (Claude 3 Haiku / Nova). Haiku 4.5·Sonnet·inference profile 은 SafeRole 권한으로
    막혀 있음(모듈 docstring 참조). 개인 계정 제거 후 텍스트 LLM 의 유일 경로.
    """
    return boto3.client("bedrock-runtime", region_name=_support_region_name())


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
