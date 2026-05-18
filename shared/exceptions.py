"""공용 예외 클래스."""


class ClinicFocusError(Exception):
    """프로젝트 최상위 예외."""
    pass


class CrawlError(ClinicFocusError):
    """크롤링 실패."""
    pass


class AdapterError(ClinicFocusError):
    """외부 서비스 어댑터 에러."""
    pass


class InsufficientDataError(ClinicFocusError):
    """데이터가 너무 빈약해서 처리 불가."""
    pass


class BedrockInvocationError(ClinicFocusError):
    """Bedrock API 호출 실패."""
    pass


class S3VectorsError(ClinicFocusError):
    """S3 Vectors 호출 실패."""
    pass


class InvalidQueryError(ClinicFocusError):
    """검색 쿼리 유효성 실패."""
    pass
