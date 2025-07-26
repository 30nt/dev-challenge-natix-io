"""
This module contains configuration settings for the application.
"""

from functools import lru_cache
from typing import Optional, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration using Pydantic BaseSettings.
    Automatically handles environment variable parsing and type conversion.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application settings
    app_name: str = "Weather Service API"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    # External API settings
    weather_api_url: str = "https://api.example.com/weather"
    weather_api_timeout: int = 10

    # Redis settings
    redis_url: str = "redis://localhost:6379"
    redis_cache_ttl: int = 3600
    redis_stale_ttl: int = 86400
    redis_decode_responses: bool = True

    # Rate limiting settings
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600

    # Cache warming settings
    enable_cache_warming: bool = True
    cache_warm_interval: int = 3600
    top_cities_count: int = 10
    cache_warm_max_tokens: int = 20
    cache_warm_min_tokens_remaining: int = 50

    # Circuit breaker settings
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 300
    circuit_breaker_expected_exception: Optional[str] = None

    # Retry settings
    retry_max_attempts: int = 3
    retry_wait_fixed: int = 1
    retry_wait_random_min: int = 0
    retry_wait_random_max: int = 2

    # CORS settings
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]


@lru_cache()
def get_settings() -> Settings:
    """
    Get the application settings.
    """
    return Settings()
