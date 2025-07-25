"""
Tests for the rate limiting service with mocked Redis.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.config import get_settings
from app.services.rate_limit_service import RateLimitService

settings = get_settings()


@pytest.mark.asyncio
class TestRateLimitService:
    """Test cases for the rate limiting service."""

    @patch("app.services.rate_limit_service.RedisStorage")
    @patch("app.services.rate_limit_service.MovingWindowRateLimiter")
    async def test_consume_rate_limit_token_success(
        self, mock_limiter_class, mock_storage_class
    ):
        """Test successful token consumption."""
        # Setup mocks
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        mock_limiter = MagicMock()
        mock_limiter.hit.return_value = True  # Token available
        mock_limiter_class.return_value = mock_limiter

        # Create rate limiter
        rate_limiter = RateLimitService()

        # Test consuming token
        result = await rate_limiter.consume_rate_limit_token("test_id")

        assert result is True
        mock_limiter.hit.assert_called_once()

    @patch("app.services.rate_limit_service.RedisStorage")
    @patch("app.services.rate_limit_service.MovingWindowRateLimiter")
    async def test_consume_rate_limit_token_exceeded(
        self, mock_limiter_class, mock_storage_class
    ):
        """Test token consumption when rate limit is exceeded."""
        # Setup mocks
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        mock_limiter = MagicMock()
        mock_limiter.hit.return_value = False  # Rate limit exceeded
        mock_limiter_class.return_value = mock_limiter

        # Create rate limiter
        rate_limiter = RateLimitService()

        # Test consuming token
        result = await rate_limiter.consume_rate_limit_token("test_id")

        assert result is False
        mock_limiter.hit.assert_called_once()

    @patch("app.services.rate_limit_service.RedisStorage")
    @patch("app.services.rate_limit_service.MovingWindowRateLimiter")
    async def test_consume_rate_limit_token_error_handling(
        self, mock_limiter_class, mock_storage_class
    ):
        """Test error handling in token consumption."""
        # Setup mocks
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        mock_limiter = MagicMock()
        mock_limiter.hit.side_effect = Exception("Test error")
        mock_limiter_class.return_value = mock_limiter

        # Create rate limiter
        rate_limiter = RateLimitService()

        # Test consuming token - should fail closed
        result = await rate_limiter.consume_rate_limit_token("test_id")

        assert result is False

    @patch("app.services.rate_limit_service.RedisStorage")
    @patch("app.services.rate_limit_service.MovingWindowRateLimiter")
    async def test_get_rate_limit_remaining(
        self, mock_limiter_class, mock_storage_class
    ):
        """Test getting remaining rate limit tokens."""
        # Setup mocks
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        mock_limiter = MagicMock()
        # Mock get_window_stats to return (window_start, current_usage)
        mock_limiter.get_window_stats.return_value = (0, 30)  # 30 used
        mock_limiter_class.return_value = mock_limiter

        # Create rate limiter
        rate_limiter = RateLimitService()

        # Test getting remaining tokens
        remaining = await rate_limiter.get_rate_limit_remaining("test_id")

        # Should be 100 - 30 = 70
        assert remaining == 70
        mock_limiter.get_window_stats.assert_called_once()

    @patch("app.services.rate_limit_service.RedisStorage")
    @patch("app.services.rate_limit_service.MovingWindowRateLimiter")
    async def test_get_rate_limit_remaining_error_handling(
        self, mock_limiter_class, mock_storage_class
    ):
        """Test error handling when getting remaining tokens."""
        # Setup mocks
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        mock_limiter = MagicMock()
        mock_limiter.get_window_stats.side_effect = Exception("Test error")
        mock_limiter_class.return_value = mock_limiter

        # Create rate limiter
        rate_limiter = RateLimitService()

        # Test getting remaining tokens - should return 0 on error
        remaining = await rate_limiter.get_rate_limit_remaining("test_id")

        assert remaining == 0

    @patch("app.services.rate_limit_service.RedisStorage")
    @patch("app.services.rate_limit_service.MovingWindowRateLimiter")
    async def test_initialization(self, mock_limiter_class, mock_storage_class):
        """Test rate limiter initialization."""
        # Setup mocks
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        mock_limiter = MagicMock()
        mock_limiter_class.return_value = mock_limiter

        # Create rate limiter
        rate_limiter = RateLimitService()

        # Verify initialization
        mock_storage_class.assert_called_once_with(settings.redis_url)
        mock_limiter_class.assert_called_once_with(mock_storage)

        # Check rate limits are parsed correctly
        assert len(rate_limiter.rate_limits) == 1
        assert rate_limiter.rate_limits[0].amount == settings.rate_limit_requests
