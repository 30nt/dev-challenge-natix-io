from typing import Optional


class WeatherServiceException(Exception):
    """Base exception for weather service."""
    pass


class RateLimitExceededException(WeatherServiceException):
    """Raised when rate limit is exceeded and request is queued."""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 300):
        self.retry_after = retry_after
        super().__init__(message)


class ExternalAPIException(WeatherServiceException):
    """Raised when external API call fails."""
    pass


class CacheException(WeatherServiceException):
    """Raised when cache operations fail."""
    pass


class CircuitBreakerOpenException(WeatherServiceException):
    """Raised when circuit breaker is open."""
    pass