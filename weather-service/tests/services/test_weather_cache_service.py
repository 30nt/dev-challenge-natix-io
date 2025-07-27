"""
Tests for the weather cache service.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.weather_cache_service import WeatherCacheService


@pytest.mark.asyncio
class TestWeatherCacheService:
    """Test cases for the weather cache service."""

    @pytest.fixture
    def mock_redis_client(self):
        """Create a mock Redis client."""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.setex = AsyncMock()
        return mock_client

    async def test_get_weather_cache_miss(self, mock_redis_client):
        """Test getting weather data when cache miss."""

        cache_service = WeatherCacheService(mock_redis_client)

        result = await cache_service.get_weather("London", "2025-07-25")

        assert result is None
        mock_redis_client.get.assert_called_once_with("weather:london:2025-07-25")

    async def test_get_weather_cache_hit(self, mock_redis_client):
        """Test getting weather data when cache hit."""

        cached_data = (
            '{"weather": [{"hour": 0, "temperature": "18", "condition": "Clear"}]}'
        )
        mock_redis_client.get.return_value = cached_data

        cache_service = WeatherCacheService(mock_redis_client)

        result = await cache_service.get_weather("London", "2025-07-25")

        assert result is not None
        assert result["weather"][0]["temperature"] == "18"
        mock_redis_client.get.assert_called_once_with("weather:london:2025-07-25")

    async def test_set_weather(self, mock_redis_client):
        """Test setting weather data in cache."""

        cache_service = WeatherCacheService(mock_redis_client)

        weather_data = {
            "result": [{"hour": 0, "temperature": "18", "condition": "Clear"}]
        }

        await cache_service.set_weather("London", "2025-07-25", weather_data)

        assert mock_redis_client.setex.call_count == 2

        first_call = mock_redis_client.setex.call_args_list[0]
        assert first_call[0][0] == "weather:london:2025-07-25"
        assert first_call[0][1] == 3600
        assert '"result"' in first_call[0][2]

    async def test_get_stale_weather(self, mock_redis_client):
        """Test getting stale weather data as fallback."""

        stale_data = (
            '{"weather": [{"hour": 0, "temperature": "17", "condition": "Cloudy"}]}'
        )
        mock_redis_client.get.side_effect = [
            None,
            stale_data,
        ]

        cache_service = WeatherCacheService(mock_redis_client)

        result = await cache_service.get_stale_weather("London", "2025-07-25")

        assert result is not None
        assert result["weather"][0]["temperature"] == "17"

        assert mock_redis_client.get.call_count == 2

    async def test_error_handling(self, mock_redis_client):
        """Test error handling in cache operations."""

        mock_redis_client.get.side_effect = Exception("Redis connection error")

        cache_service = WeatherCacheService(mock_redis_client)

        result = await cache_service.get_weather("London", "2025-07-25")

        assert result is None
