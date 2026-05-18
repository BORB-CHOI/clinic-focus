class BedrockInvocationError(Exception):
    """Bedrock API 호출 실패."""


class InsufficientDataError(Exception):
    """크롤링 데이터가 너무 빈약해 분류 불가."""


class DescriptionValidationError(Exception):
    """generate_description 출력이 주체 명시·출처 태그 의무를 위반."""


class S3VectorsError(Exception):
    """S3 Vectors PutVectors / QueryVectors 호출 실패."""


class TextTooLongError(Exception):
    """임베딩 입력 텍스트가 8192 토큰 초과."""


class ImageNotFoundError(Exception):
    """S3 이미지 URL 무효 또는 접근 불가."""


class InvalidQueryError(Exception):
    """query_text와 lat/lng 둘 다 없는 검색 요청."""


class InsufficientFeedbackError(Exception):
    """피드백이 통계적으로 유의미하지 않은 수준 (3건 미만)."""
