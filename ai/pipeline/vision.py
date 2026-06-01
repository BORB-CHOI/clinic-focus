"""
ai/vision.py — Bedrock Vision 이미지 분석 모듈

책임:
- 병원 사이트 이미지를 Bedrock Claude Vision으로 분석
- 의료기기·시술 장비 식별, 이미지 카테고리 분류, 확신도 산출
- OCR 은 Bedrock Vision 이 흡수 (한국어 미지원으로 Textract 미사용)
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
from ai.core.aws_clients import get_s3_client_for_images
from ai.core.exceptions import BedrockInvocationError, ImageNotFoundError
from shared.models import ImageAnalysisResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 환경변수
# ---------------------------------------------------------------------------

_DEFAULT_MAX_VISION_IMAGES = 10
_DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# 이미지 카테고리 Literal 검증용 목록
# ---------------------------------------------------------------------------

_VALID_CATEGORIES = {"일반 진료", "미용 시술", "장비 사진", "건물·내부", "기타"}
_FALLBACK_CATEGORY = "기타"

# ---------------------------------------------------------------------------
# Vision 분석 프롬프트
# ---------------------------------------------------------------------------

_VISION_PROMPT = """\
아래는 한국 병원·의원 웹사이트에서 가져온 이미지입니다. 웹페이지를 위→아래로
스크롤하며 찍은 화면 캡처일 수도, 사이트에 올라온 개별 사진일 수도 있습니다.

**글자만 읽지 마세요(이건 OCR 작업이 아닙니다).** 화면에 무엇이 보이는지를
**시각적으로 해석**하세요 — 시술 장면, 전후 비교 사진, 장비 클로즈업, 진료실·
대기실 같은 공간, 인포그래픽·3D 그림 등. 그 위에 보이는 글자도 함께 적으세요.

다른 텍스트 없이 아래 JSON만 반환하세요.

{
  "scene": "이미지에 시각적으로 보이는 장면을 1~3문장으로 묘사 (어떤 사진·그림·시술 장면·장비·공간인지). 의료와 무관하면 본 그대로 적음",
  "detected_procedures": ["이미지에서 시각적으로 드러나는 시술·진료 항목 이름 (한국어, 없으면 빈 배열)"],
  "detected_devices": ["보이는 의료기기·시술 장비 이름 (한국어, 없으면 빈 배열)"],
  "in_image_text": "이미지·배너·간판에 박혀 보이는 핵심 텍스트(병원명·시술명·강조 문구) 위주로 짧게 (본문 단락 전체를 옮기지 말 것, 없으면 빈 문자열)",
  "image_category": "일반 진료 | 미용 시술 | 장비 사진 | 건물·내부 | 기타 중 하나",
  "confidence": 0.0~1.0 사이 숫자 (판단 확신도)
}

image_category 기준 (이미지의 지배적 성격 하나):
- 일반 진료: 진료실, 상담, 채혈, 처치 등 일반 의료 행위
- 미용 시술: 보톡스·필러·레이저 등 미용 목적 시술
- 장비 사진: 의료기기·시술 장비가 화면의 중심
- 건물·내부: 외관, 로비, 대기실, 접수처 등 공간
- 기타: 위에 안 맞거나 의료와 무관 (로고·메뉴바만 있는 화면 포함)

주의: 환자 개인 식별 정보·의료진 얼굴 매칭은 하지 마세요. 추측·평가 없이
보이는 그대로 객관적으로만 적으세요.\
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


def _looks_like_image(data: bytes) -> bool:
    """매직 넘버로 실제 이미지 바이트인지 판정 (HTML 차단페이지 등 걸러냄)."""
    return (
        data[:3] == b"\xff\xd8\xff"          # JPEG
        or data[:4] == b"\x89PNG"             # PNG
        or data[:3] == b"GIF"                 # GIF
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")  # WebP
    )


def _download_http_image(url: str) -> bytes:
    """HTTP/HTTPS URL에서 이미지 바이트를 다운로드.

    많은 워드프레스/CMS 사이트가 Referer 없는 직접 요청을 핫링크 차단해 이미지
    대신 HTML 페이지를 돌려준다(그대로 Bedrock 에 넣으면 "Could not process image").
    브라우저 유사 헤더 + 자기 출처 Referer 로 우회하고, 받은 바이트가 진짜
    이미지인지 매직 넘버로 검증해 HTML 류는 **Bedrock 호출 전에** 걸러낸다.

    Raises:
        ImageNotFoundError: HTTP·네트워크 오류 또는 이미지가 아닌 응답
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}/"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/png,image/*,*/*;q=0.8",
            "Referer": origin,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        raise ImageNotFoundError(f"HTTP 오류 {exc.code}: {url}") from exc
    except urllib.error.URLError as exc:
        raise ImageNotFoundError(f"URL 접근 불가: {url} — {exc.reason}") from exc
    except Exception as exc:
        raise ImageNotFoundError(f"이미지 다운로드 실패: {url} — {exc}") from exc

    if not _looks_like_image(data):
        # 핫링크 차단 HTML·빈 응답 등 — Bedrock 비용 낭비 전에 차단
        raise ImageNotFoundError(f"이미지가 아닌 응답(핫링크 차단 추정): {url}")
    return data


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

        detected_procedures: list[str] = parsed.get("detected_procedures", [])
        if not isinstance(detected_procedures, list):
            detected_procedures = []
        detected_procedures = [str(p) for p in detected_procedures if p]

        scene = parsed.get("scene", "")
        scene = str(scene).strip() if scene else ""
        in_image_text = parsed.get("in_image_text", "")
        in_image_text = str(in_image_text).strip() if in_image_text else ""

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
            scene=scene,
            detected_procedures=detected_procedures,
            in_image_text=in_image_text,
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


# ---------------------------------------------------------------------------
# `<img>` 태그 필터 — 로고·배너·아이콘 제거
# ---------------------------------------------------------------------------

# 파일명·경로에 이런 토큰이 들어가면 콘텐츠가 아니라 장식(로고·배너·아이콘·버튼·
# 공용 UI 스프라이트)일 확률이 높다. 구 방식이 vision=0 으로 망한 핵심 원인이라
# 하이브리드에서 `<img>` 는 보조로만 쓰되 이 쓰레기를 먼저 걷어낸다.
_IMG_JUNK_TOKENS = (
    "logo", "banner", "icon", "btn", "button", "bg_", "_bg", "sprite",
    "favicon", "header", "footer", "gnb", "nav", "menu", "bullet", "arrow",
    "dot", "blank", "spacer", "loading", "kakao", "naver", "facebook",
    "instagram", "youtube", "blog_", "sns", "top_", "quick", "badge",
    "watermark", "txt_", "tit_", "bul_", "ico_", "img_logo",
)
_IMG_GOOD_EXT = (".jpg", ".jpeg", ".png", ".webp")


def filter_content_image_urls(urls: list[str]) -> list[str]:
    """`<img>` URL 목록에서 로고·배너·아이콘 류를 걷어내고 콘텐츠성 이미지만 남긴다.

    크롤된 `<img>` 는 대부분 로고·히어로배너라 그대로 Vision 에 넣으면 noise(=구
    방식 vision=0 원인). 파일명 휴리스틱으로 거른다. 정확한 판별은 Vision 이
    하지만, 호출 비용을 줄이려 명백한 장식은 사전 제거한다. 순서 보존·중복 제거.
    """
    seen: set[str] = set()
    kept: list[str] = []
    for url in urls:
        if not url or url in seen:
            continue
        seen.add(url)
        low = url.lower()
        path = urlparse(low).path
        if path.endswith(".gif") or path.endswith(".svg"):  # 거의 아이콘·애니
            continue
        if any(tok in low for tok in _IMG_JUNK_TOKENS):
            continue
        # 확장자가 명확한 사진류만 (data URI·확장자 없는 트래킹 픽셀 등 제외)
        if not any(path.endswith(ext) for ext in _IMG_GOOD_EXT):
            continue
        kept.append(url)
    return kept


# ---------------------------------------------------------------------------
# Vision 호출 코어 (URL·스크린샷 공용)
# ---------------------------------------------------------------------------


def _analyze_one_image(
    image_bytes: bytes, media_type: str, source_label: str
) -> ImageAnalysisResult:
    """이미지 바이트 1장을 Bedrock Vision 으로 분석 → ImageAnalysisResult.

    URL 다운로드(analyze_images)와 스크린샷 bytes(analyze_screenshots)가 공유한다.

    Raises:
        BedrockInvocationError: Bedrock Vision API 호출 자체 실패.
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    try:
        response = bedrock_client.invoke_model_with_image(
            prompt=_VISION_PROMPT,
            image_b64=image_b64,
            media_type=media_type,
        )
    except Exception as exc:
        raise BedrockInvocationError(
            f"Bedrock Vision 호출 실패 (src={source_label}): {exc}"
        ) from exc
    return _parse_vision_response(response, source_label)


# ---------------------------------------------------------------------------
# 공개 함수
# ---------------------------------------------------------------------------


def analyze_images(
    image_urls: list[str],
) -> list[ImageAnalysisResult]:
    """이미지 URL 리스트를 Bedrock Vision으로 분석해 ImageAnalysisResult 리스트 반환.

    동작:
    1. MAX_VISION_IMAGES 환경변수(기본 10) 초과분 앞에서 잘라냄
    2. 각 URL: 다운로드 → Bedrock Vision 호출(장면 해석) → 파싱
    3. 개별 이미지 오류는 건너뛰고 나머지 계속 처리

    하이브리드에서 이 경로는 **`<img>` 보조용** — 호출 전 filter_content_image_urls
    로 로고·배너를 거른 URL 을 넘기는 걸 권장한다. OCR 이 아니라 장면 해석이다.

    Args:
        image_urls: 분석할 이미지 URL 목록 (s3:// 또는 http/https)

    Returns:
        성공적으로 분석된 이미지의 ImageAnalysisResult 리스트

    Raises:
        BedrockInvocationError: Bedrock Vision API 호출 자체가 실패했을 때
    """
    max_images = _get_max_vision_images()
    if len(image_urls) > max_images:
        logger.info(
            "이미지 %d개 중 앞 %d개만 처리 (MAX_VISION_IMAGES=%d)",
            len(image_urls), max_images, max_images,
        )
        image_urls = image_urls[:max_images]

    results: list[ImageAnalysisResult] = []
    total = len(image_urls)

    for idx, url in enumerate(image_urls, start=1):
        logger.debug("이미지 분석 시작 [%d/%d] url=%s", idx, total, url)

        # 1. 이미지 다운로드 (개별 실패는 건너뜀)
        try:
            image_bytes = _download_image(url)
        except ImageNotFoundError as exc:
            logger.warning("이미지 다운로드 실패, 건너뜀: %s", exc)
            continue

        media_type = _detect_media_type(image_bytes, url)
        # 개별 이미지의 Bedrock 실패(로고가 필터를 빠져나가 "Could not process
        # image" 등)는 건너뛴다 — 한 장 때문에 배치 전체를 버리지 않는다.
        try:
            result = _analyze_one_image(image_bytes, media_type, url)
        except BedrockInvocationError as exc:
            logger.warning("이미지 Vision 호출 실패, 건너뜀 [%d/%d]: %s", idx, total, exc)
            continue
        results.append(result)

        logger.info(
            "이미지 분석 완료 [%d/%d] cat=%s proc=%s dev=%s conf=%.2f url=%s",
            idx, total, result.image_category, result.detected_procedures,
            result.detected_devices, result.confidence, url,
        )

    logger.info("analyze_images 완료: 입력 %d개 → 성공 %d개", total, len(results))
    return results


def analyze_screenshots(
    screenshots: list[bytes], *, source_prefix: str = "screenshot"
) -> list[ImageAnalysisResult]:
    """풀페이지 스크롤 스크린샷 PNG bytes 들을 Bedrock Vision 으로 장면 해석.

    하이브리드의 **주력 경로** — 렌더된 화면(시술사진·전후·장비·CSS배경·이미지에
    박힌 텍스트·팝업)을 그대로 본다. 구 `<img>` 방식이 못 보던 것들이 여기 다 잡힌다.

    MAX_VISION_IMAGES 로 장수를 제한한다. 다운로드가 없어 URL 경로보다 빠르다.

    Args:
        screenshots: PNG bytes 리스트 (be.core.browser_manager.screenshot_page_scroll 산출).
        source_prefix: image_url 합성 라벨 접두사 ("screenshot:tile-N").
    """
    max_images = _get_max_vision_images()
    shots = screenshots[:max_images]
    results: list[ImageAnalysisResult] = []
    total = len(shots)
    for idx, png in enumerate(shots, start=1):
        if not png:
            continue
        label = f"{source_prefix}:tile-{idx}"
        try:
            result = _analyze_one_image(png, "image/png", label)
        except BedrockInvocationError as exc:
            logger.warning("스크린샷 Vision 호출 실패, 건너뜀 [%d/%d]: %s", idx, total, exc)
            continue
        results.append(result)
        logger.info(
            "스크린샷 분석 완료 [%d/%d] cat=%s proc=%s scene=%.30s conf=%.2f",
            idx, total, result.image_category, result.detected_procedures,
            result.scene, result.confidence,
        )
    logger.info("analyze_screenshots 완료: 입력 %d장 → 성공 %d장", total, len(results))
    return results


# ---------------------------------------------------------------------------
# 멀티이미지 배칭 — 한 병원의 타일+사진을 1회 호출로 (속도)
# ---------------------------------------------------------------------------

_VISION_BATCH_PROMPT = """\
아래 이미지들은 **한 병원·의원 사이트에서 모은 것**입니다 — 웹페이지를 위→아래로
스크롤하며 찍은 화면 캡처 타일들 + 사이트에 올라온 개별 사진이 섞여 있을 수 있습니다.

**글자만 읽지 말고(OCR 아님), 화면에 무엇이 보이는지 시각적으로 해석**하세요 —
시술 장면, 전후 비교, 장비 클로즈업, 진료실·대기실 같은 공간, 인포그래픽·3D 그림 등.
**여러 장을 종합해서 이 병원 사이트 전체가 시각적으로 무엇을 강조하는지** 한 개의
JSON 으로만 답하세요(다른 텍스트 없이).

{
  "scene": "이미지들을 종합해 이 사이트가 시각적으로 보여주는 것을 2~4문장으로 묘사",
  "detected_procedures": ["전체에서 시각적으로 드러나는 시술·진료 항목 (한국어, 합집합, 없으면 빈 배열)"],
  "detected_devices": ["보이는 의료기기·시술 장비 이름 (한국어, 합집합, 없으면 빈 배열)"],
  "in_image_text": "이미지·배너·간판에 박혀 보이는 핵심 텍스트(병원명·시술명·강조 문구) 위주로 짧게 (없으면 빈 문자열)",
  "image_category": "일반 진료 | 미용 시술 | 장비 사진 | 건물·내부 | 기타 중 가장 지배적인 하나",
  "confidence": 0.0~1.0 사이 숫자
}

주의: 환자 개인 식별 정보·의료진 얼굴 매칭은 하지 마세요. 추측·평가 없이 보이는 그대로.\
"""


def download_content_images(urls: list[str]) -> list[tuple[bytes, str]]:
    """필터된 `<img>` URL 들을 (bytes, media_type) 로 다운로드. 핫링크 차단 HTML·실패는 스킵.

    배칭 호출에 넣을 이미지 바이트를 모은다 (스크린샷 bytes 와 합쳐 1회 호출).
    """
    out: list[tuple[bytes, str]] = []
    for url in urls:
        try:
            data = _download_image(url)
        except ImageNotFoundError as exc:
            logger.info("img 다운로드 스킵: %s", exc)
            continue
        out.append((data, _detect_media_type(data, url)))
    return out


def analyze_batch(
    images: list[tuple[bytes, str]], *, label: str = "batch"
) -> ImageAnalysisResult | None:
    """한 병원의 이미지 여러 장(스크린샷 타일 + 개별 사진)을 **1회 Vision 호출**로 종합 분석.

    이미지당 1콜(순차) 대신 한 메시지에 모아 호출 → 라운드트립 1회로 병원당 수십 초 절감.
    결과는 종합된 ImageAnalysisResult 1건. 입력이 없으면 None.

    Raises:
        BedrockInvocationError: Bedrock 호출 자체 실패.
    """
    images = [(b, mt) for b, mt in images if b][: _get_max_vision_images()]
    if not images:
        return None
    payload = [(base64.b64encode(b).decode("utf-8"), mt) for b, mt in images]
    try:
        response = bedrock_client.invoke_model_with_images(_VISION_BATCH_PROMPT, payload)
    except Exception as exc:
        raise BedrockInvocationError(f"Bedrock Vision 배치 호출 실패 (src={label}): {exc}") from exc
    result = _parse_vision_response(response, label)
    logger.info(
        "배치 분석 완료 [%s] 이미지%d장 → cat=%s proc=%s dev=%s conf=%.2f",
        label, len(images), result.image_category, result.detected_procedures,
        result.detected_devices, result.confidence,
    )
    return result
