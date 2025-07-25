import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    app_name: str = os.getenv("APP_NAME", "Weather Service API")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")

    weather_api_url: str = os.getenv(
        "WEATHER_API_URL", "https://api.example.com/weather"
    )
    weather_api_timeout: int = int(os.getenv("WEATHER_API_TIMEOUT", "10"))

    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_cache_ttl: int = int(os.getenv("REDIS_CACHE_TTL", "3600"))  # 1 hour
    redis_stale_ttl: int = int(os.getenv("REDIS_STALE_TTL", "86400"))  # 24 hours
    redis_decode_responses: bool = (
        os.getenv("REDIS_DECODE_RESPONSES", "true").lower() == "true"
    )

    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    rate_limit_window: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 hour

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    enable_cache_warming: bool = (
        os.getenv("ENABLE_CACHE_WARMING", "true").lower() == "true"
    )
    cache_warm_interval: int = int(os.getenv("CACHE_WARM_INTERVAL", "3600"))  # 1 hour
    top_cities_count: int = int(os.getenv("TOP_CITIES_COUNT", "10"))
    cache_warm_max_tokens: int = int(
        os.getenv("CACHE_WARM_MAX_TOKENS", "20")
    )  # Max 20% of rate limit
    cache_warm_min_tokens_remaining: int = int(
        os.getenv("CACHE_WARM_MIN_TOKENS_REMAINING", "50")
    )  # Keep 50 tokens for users

    circuit_breaker_failure_threshold: int = int(
        os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
    )
    circuit_breaker_recovery_timeout: int = int(
        os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "300")
    )  # 5 minutes
    circuit_breaker_expected_exception: Optional[str] = os.getenv(
        "CIRCUIT_BREAKER_EXPECTED_EXCEPTION"
    )

    retry_max_attempts: int = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    retry_wait_fixed: int = int(os.getenv("RETRY_WAIT_FIXED", "1"))
    retry_wait_random_min: int = int(os.getenv("RETRY_WAIT_RANDOM_MIN", "0"))
    retry_wait_random_max: int = int(os.getenv("RETRY_WAIT_RANDOM_MAX", "2"))

    cors_origins: list[str] = os.getenv("CORS_ORIGINS", '["*"]').strip('"[]').split(",")
    cors_allow_credentials: bool = (
        os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    )
    cors_allow_methods: list[str] = (
        os.getenv("CORS_ALLOW_METHODS", '["*"]').strip('"[]').split(",")
    )
    cors_allow_headers: list[str] = (
        os.getenv("CORS_ALLOW_HEADERS", '["*"]').strip('"[]').split(",")
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
