"""
Tests for the configuration module.
"""

import os
from unittest.mock import patch

from app.config import Settings, get_settings


class TestConfig:
    """Test suite for application configuration management.

    Validates settings loading from environment variables,
    default values, and singleton pattern implementation.
    """

    def test_default_settings(self):
        """Test default configuration values.

        Verifies that when no environment variables are set,
        the application uses sensible defaults for rate limiting,
        caching, and other operational parameters.
        """
        settings = Settings()

        assert settings.app_name == "Weather Service API"
        assert settings.app_version == "1.0.0"
        assert settings.rate_limit_requests == 100
        assert settings.rate_limit_window == 3600
        assert settings.redis_cache_ttl == 3600
        assert settings.redis_stale_ttl == 86400

    @patch.dict(os.environ, {"RATE_LIMIT_REQUESTS": "50", "RATE_LIMIT_WINDOW": "1800"})
    def test_settings_from_env(self):
        """Test environment variable override functionality.

        Validates that Pydantic BaseSettings correctly loads
        and type-converts environment variables, allowing
        deployment-specific configuration.
        """
        settings = Settings()

        assert settings.rate_limit_requests == 50
        assert settings.rate_limit_window == 1800

    def test_get_settings_singleton(self):
        """Test singleton pattern for settings instance.

        Ensures that multiple calls to get_settings() return
        the same instance, preventing redundant parsing and
        maintaining consistent configuration throughout the app.
        """
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    @patch.dict(
        os.environ, {"CORS_ORIGINS": '["https://example.com","https://app.com"]'}
    )
    def test_cors_origins_parsing(self):
        """Test JSON parsing for complex configuration values.

        Validates that JSON-encoded environment variables are
        properly parsed into Python data structures, enabling
        list and object configurations via environment.
        """
        settings = Settings()

        assert settings.cors_origins == ["https://example.com", "https://app.com"]

    def test_redis_url_format(self):
        """Test Redis connection URL construction.

        Ensures the Redis URL follows the expected format
        with proper protocol prefix and includes a valid
        host specification for connection establishment.
        """
        settings = Settings()

        assert settings.redis_url.startswith("redis://")
        assert "localhost" in settings.redis_url or "127.0.0.1" in settings.redis_url
