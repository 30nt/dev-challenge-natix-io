"""Weather service exceptions."""

from .common import (
    WeatherServiceException,
    RateLimitExceededException,
    ExternalAPIException,
    CacheException,
    CircuitBreakerOpenException,
    ValidationError,
)

__all__ = [
    "WeatherServiceException",
    "RateLimitExceededException",
    "ExternalAPIException",
    "CacheException",
    "CircuitBreakerOpenException",
    "ValidationError",
]
