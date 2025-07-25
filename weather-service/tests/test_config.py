"""
Tests for the configuration module.
"""

import os
from unittest.mock import patch

from app.config import Settings, get_settings


class TestConfig:
    """Test cases for configuration settings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()

        assert settings.app_name == "Weather Service API"
        assert settings.app_version == "1.0.0"
        assert settings.rate_limit_requests == 100
        assert settings.rate_limit_window == 3600
        assert settings.redis_cache_ttl == 3600
        assert settings.redis_stale_ttl == 86400

    @patch.dict(os.environ, {"RATE_LIMIT_REQUESTS": "50", "RATE_LIMIT_WINDOW": "1800"})
    def test_settings_from_env(self):
        """Test settings loaded from environment variables."""
        settings = Settings()

        assert settings.rate_limit_requests == 50
        assert settings.rate_limit_window == 1800

    def test_get_settings_singleton(self):
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    @patch.dict(
        os.environ, {"CORS_ORIGINS": '["https://example.com","https://app.com"]'}
    )
    def test_cors_origins_parsing(self):
        """Test CORS origins list parsing from environment."""
        settings = Settings()

        assert settings.cors_origins == ["https://example.com", "https://app.com"]

    def test_redis_url_format(self):
        """Test Redis URL is properly formatted."""
        settings = Settings()

        assert settings.redis_url.startswith("redis://")
        assert "localhost" in settings.redis_url or "127.0.0.1" in settings.redis_url
