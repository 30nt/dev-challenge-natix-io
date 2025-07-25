class WeatherServiceException(Exception):
    """Base exception for weather service."""
    def __init__(self, message: str):
        super().__init__(message)


class RateLimitExceededException(WeatherServiceException):
    """Raised when rate limit is exceeded and request is queued."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 300):
        self.retry_after = retry_after
        super().__init__(message)


class ExternalAPIException(WeatherServiceException):
    """Raised when external API call fails."""


class CacheException(WeatherServiceException):
    """Raised when cache operations fail."""


class CircuitBreakerOpenException(WeatherServiceException):
    """Raised when circuit breaker is open."""


class ValidationError(WeatherServiceException):
    """Raised when validation fails."""

