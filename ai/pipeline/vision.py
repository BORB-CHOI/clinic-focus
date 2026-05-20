"""
ai/vision.py — Bedrock Vision + Textract 이미지 분석 모듈

책임:
- 병원 사이트 이미지를 Bedrock Claude Vision으로 분석
- 의료기기·시술 장비 식별, 이미지 카테고리 분류, 확신도 산출
- extract_text=True 시 Textract OCR 보조 (결과는 로깅 전용)
- MAX_VISION_IMAGES 환경변수로 호출 비용 통제
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

from ai.core import bedrock_client
from ai.core.aws_clients import get_s3_client_for_images, get_textract_client
from ai.core.exceptions import BedrockInvocationError, ImageNotFoundError
from shared.models import ImageAnalysisResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 환경변수
# ---------------------------------------------------------------------------

_DEFAULT_MAX_VISION_IMAGES = 10
_DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# ---------------------------------------------------------------------------
# 이미지 카테고리 Literal 검증용 목록
# ---------------------------------------------------------------------------

_VALID_CATEGORIES = {"일반 진료", "미용 시술", "장비 사진", "건물·내부", "기타"}
_FALLBACK_CATEGORY = "기타"

# ---------------------------------------------------------------------------
# Vision 분석 프롬프트
# ---------------------------------------------------------------------------

_VISION_PROMPT = """\
이 이미지는 한국 병원·의원 웹사이트에서 수집된 사진입니다.
아래 세 가지를 JSON 형식으로 답해주세요. 다른 텍스트 없이 JSON만 반환하세요.

{
  "detected_devices": ["보이는 의료기기·시술 장비 이름 (한국어, 없으면 빈 배열)"],
  "image_category": "일반 진료 | 미용 시술 | 장비 사진 | 건물·내부 | 기타 중 하나",
  "confidence": 0.0~1.0 사이 숫자 (판단 확신도)
}

분류 기준:
- 일반 진료: 진료실, 상담, 채혈, 처치 등 일반 의료 행위 사진
- 미용 시술: 보톡스·필러·레이저 등 미용 목적 시술 사진
- 장비 사진: 의료기기·시술 장비만 단독으로 찍힌 사진
- 건물·내부: 외관, 로비, 대기실, 접수처 등 공간 사진
- 기타: 위 범주에 해당하지 않거나 의료와 무관한 사진

주의: 환자 개인 식별 정보를 언급하지 마세요. 의료진 얼굴 매칭도 하지 마세요.\
"""

# ---------------------------------------------------------------------------
# 내부 유틸
# ---------------------------------------------------------------------------


def _get_max_vision_images() -> int:
    """MAX_VISION_IMAGES 환경변수를 읽어 정수로 반환. 파싱 실패 시 기본값 10."""
    raw = os.getenv("MAX_VISION_IMAGES", str(_DEFAULT_MAX_VISION_IMAGES))
    try:
        val = int(raw)
        return val if val > 0 else _DEFAULT_MAX_VISION_IMAGES
    except ValueError:
        logger.warning("MAX_VISION_IMAGES 파싱 실패 (%s), 기본값 %d 사용", raw, _DEFAULT_MAX_VISION_IMAGES)
        return _DEFAULT_MAX_VISION_IMAGES


def _url_cache_key(url: str) -> str:
    """URL 해시 기반 캐시 키 생성 (동일 이미지 재분석 방지용 식별자)."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _detect_media_type(data: bytes, url: str) -> str:
    """바이트 매직 넘버 또는 URL 확장자로 media_type 판별."""
    # JPEG: FF D8 FF
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    # PNG: 89 50 4E 47
    if data[:4] == b"\x89PNG":
        return "image/png"
    # GIF: 47 49 46
    if data[:3] == b"GIF":
        return "image/gif"
    # WebP: RIFF....WEBP
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"

    # 확장자 폴백
    path = urlparse(url).path.lower()
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".gif"):
        return "image/gif"
    if path.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"


def _download_s3_image(url: str) -> bytes:
    """s3://bucket/key 형식 URL에서 이미지 바이트를 다운로드.

    Raises:
        ImageNotFoundError: 버킷·키 부재 또는 접근 불가
    """
    parsed = urlparse(url)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    s3 = get_s3_client_for_images()
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()
    except Exception as exc:
        raise ImageNotFoundError(f"S3 이미지 접근 실패: {url} — {exc}") from exc


def _download_http_image(url: str) -> bytes:
    """HTTP/HTTPS URL에서 이미지 바이트를 다운로드.

    Raises:
        ImageNotFoundError: HTTP 오류 또는 네트워크 오류
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "clinic-focus-vision/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise ImageNotFoundError(f"HTTP 오류 {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise ImageNotFoundError(f"URL 접근 불가: {url} — {exc.reason}") from exc
    except Exception as exc:
        raise ImageNotFoundError(f"이미지 다운로드 실패: {url} — {exc}") from exc


def _download_image(url: str) -> bytes:
    """URL 스킴에 따라 S3 또는 HTTP로 이미지 다운로드."""
    if url.startswith("s3://"):
        return _download_s3_image(url)
    return _download_http_image(url)


def _parse_vision_response(response: dict, image_url: str) -> ImageAnalysisResult:
    """Bedrock Vision 응답 dict를 ImageAnalysisResult로 파싱.

    JSON 파싱 실패 또는 필드 누락 시 안전한 기본값으로 폴백.
    """
    try:
        raw_text: str = response["content"][0]["text"]

        # JSON 블록만 추출 (```json ... ``` 감싸는 경우 대비)
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # 첫 줄(```json) 과 마지막 줄(```) 제거
            inner = "\n".join(lines[1:-1]) if len(lines) > 2 else text
            text = inner.strip()

        parsed = json.loads(text)

        detected_devices: list[str] = parsed.get("detected_devices", [])
        if not isinstance(detected_devices, list):
            detected_devices = []
        # 문자열 항목만 유지
        detected_devices = [str(d) for d in detected_devices if d]

        category: str = parsed.get("image_category", _FALLBACK_CATEGORY)
        if category not in _VALID_CATEGORIES:
            logger.warning(
                "알 수 없는 image_category '%s' → '%s'로 대체 (url=%s)",
                category,
                _FALLBACK_CATEGORY,
                image_url,
            )
            category = _FALLBACK_CATEGORY

        raw_confidence = parsed.get("confidence", 0.5)
        try:
            confidence = float(raw_confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (TypeError, ValueError):
            confidence = 0.5

        return ImageAnalysisResult(
            image_url=image_url,
            detected_devices=detected_devices,
            image_category=category,  # type: ignore[arg-type]
            confidence=confidence,
        )

    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning(
            "Vision 응답 파싱 실패, 기본값 사용 (url=%s): %s", image_url, exc
        )
        return ImageAnalysisResult(
            image_url=image_url,
            detected_devices=[],
            image_category=_FALLBACK_CATEGORY,  # type: ignore[arg-type]
            confidence=0.0,
        )


def _run_textract_ocr(image_bytes: bytes, url: str) -> None:
    """Textract AnalyzeDocument로 텍스트를 추출해 로그에 남긴다.

    결과를 ImageAnalysisResult에 포함하지 않음 (현재 모델에 텍스트 필드 없음).
    Textract 호출 실패는 전체 흐름에 영향을 주지 않는다.
    """
    try:
        textract = get_textract_client()
        response = textract.analyze_document(
            Document={"Bytes": image_bytes},
            FeatureTypes=["TABLES", "FORMS"],
        )
        blocks = response.get("Blocks", [])
        lines = [
            b["Text"]
            for b in blocks
            if b.get("BlockType") == "LINE" and b.get("Text")
        ]
        extracted = " | ".join(lines[:20])  # 로그 길이 제한
        logger.info("Textract OCR (url=%s): %s", url, extracted if extracted else "(텍스트 없음)")
    except Exception as exc:
        logger.warning("Textract 호출 실패, 건너뜀 (url=%s): %s", url, exc)


# ---------------------------------------------------------------------------
# 공개 함수
# ---------------------------------------------------------------------------


def analyze_images(
    image_urls: list[str],
    extract_text: bool = False,
) -> list[ImageAnalysisResult]:
    """이미지 URL 리스트를 Bedrock Vision으로 분석해 ImageAnalysisResult 리스트 반환.

    동작:
    1. MAX_VISION_IMAGES 환경변수(기본 10) 초과분 앞에서 잘라냄
    2. 각 URL: 다운로드 → base64 인코딩 → Bedrock Vision 호출 → 파싱
    3. extract_text=True면 Textract OCR 보조 호출 (결과는 로깅만)
    4. 개별 이미지 오류는 건너뛰고 나머지 계속 처리

    Args:
        image_urls: 분석할 이미지 URL 목록 (s3:// 또는 http/https)
        extract_text: True면 Textract OCR 보조 실행

    Returns:
        성공적으로 분석된 이미지의 ImageAnalysisResult 리스트

    Raises:
        BedrockInvocationError: Bedrock Vision API 호출 자체가 실패했을 때
        ImageNotFoundError: 이미지 다운로드 실패 (개별 이미지 건너뜀 처리하면 외부로 전파 안 됨)
    """
    max_images = _get_max_vision_images()
    if len(image_urls) > max_images:
        logger.info(
            "이미지 %d개 중 앞 %d개만 처리 (MAX_VISION_IMAGES=%d)",
            len(image_urls),
            max_images,
            max_images,
        )
        image_urls = image_urls[:max_images]

    results: list[ImageAnalysisResult] = []
    total = len(image_urls)

    for idx, url in enumerate(image_urls, start=1):
        cache_key = _url_cache_key(url)
        logger.debug("이미지 분석 시작 [%d/%d] key=%s url=%s", idx, total, cache_key, url)

        # 1. 이미지 다운로드
        try:
            image_bytes = _download_image(url)
        except ImageNotFoundError as exc:
            logger.warning("이미지 다운로드 실패, 건너뜀: %s", exc)
            continue

        # 2. base64 인코딩 + media_type 판별
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        media_type = _detect_media_type(image_bytes, url)

        # 3. Bedrock Vision 호출
        try:
            response = bedrock_client.invoke_model_with_image(
                prompt=_VISION_PROMPT,
                image_b64=image_b64,
                media_type=media_type,
            )
        except Exception as exc:
            raise BedrockInvocationError(
                f"Bedrock Vision 호출 실패 (url={url}): {exc}"
            ) from exc

        # 4. 응답 파싱 → ImageAnalysisResult
        result = _parse_vision_response(response, url)
        results.append(result)

        logger.info(
            "이미지 분석 완료 [%d/%d] category=%s devices=%s confidence=%.2f url=%s",
            idx,
            total,
            result.image_category,
            result.detected_devices,
            result.confidence,
            url,
        )

        # 5. Textract OCR (보조, extract_text=True 시)
        if extract_text:
            _run_textract_ocr(image_bytes, url)

    logger.info(
        "analyze_images 완료: 입력 %d개 → 성공 %d개",
        total,
        len(results),
    )
    return results
