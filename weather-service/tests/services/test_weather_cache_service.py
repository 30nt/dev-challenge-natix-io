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
        # Create cache service with mock Redis
        cache_service = WeatherCacheService(mock_redis_client)

        # Test cache miss
        result = await cache_service.get_weather("London", "2025-07-25")

        assert result is None
        mock_redis_client.get.assert_called_once_with("weather:london:2025-07-25")

    async def test_get_weather_cache_hit(self, mock_redis_client):
        """Test getting weather data when cache hit."""
        # Set up mock to return cached data
        cached_data = (
            '{"weather": [{"hour": 0, "temperature": "18", "condition": "Clear"}]}'
        )
        mock_redis_client.get.return_value = cached_data

        # Create cache service with mock Redis
        cache_service = WeatherCacheService(mock_redis_client)

        # Test cache hit
        result = await cache_service.get_weather("London", "2025-07-25")

        assert result is not None
        assert result["weather"][0]["temperature"] == "18"
        mock_redis_client.get.assert_called_once_with("weather:london:2025-07-25")

    async def test_set_weather(self, mock_redis_client):
        """Test setting weather data in cache."""
        # Create cache service with mock Redis
        cache_service = WeatherCacheService(mock_redis_client)

        # Test data
        weather_data = {
            "result": [{"hour": 0, "temperature": "18", "condition": "Clear"}]
        }

        # Set weather in cache
        await cache_service.set_weather("London", "2025-07-25", weather_data)

        # Verify Redis setex was called correctly
        # Note: set_weather calls setex twice - once for data, once for metadata
        assert mock_redis_client.setex.call_count == 2

        # Check the first call (weather data)
        first_call = mock_redis_client.setex.call_args_list[0]
        assert first_call[0][0] == "weather:london:2025-07-25"  # key
        assert first_call[0][1] == 3600  # ttl (from settings)
        assert '"result"' in first_call[0][2]  # JSON data

    async def test_get_stale_weather(self, mock_redis_client):
        """Test getting stale weather data as fallback."""
        # Set up mock to return stale data
        stale_data = (
            '{"weather": [{"hour": 0, "temperature": "17", "condition": "Cloudy"}]}'
        )
        mock_redis_client.get.side_effect = [
            None,
            stale_data,
        ]  # First call returns None, second returns data

        # Create cache service with mock Redis
        cache_service = WeatherCacheService(mock_redis_client)

        # Test getting stale weather
        result = await cache_service.get_stale_weather("London", "2025-07-25")

        assert result is not None
        assert result["weather"][0]["temperature"] == "17"
        # Should check both normal and stale keys
        assert mock_redis_client.get.call_count == 2

    async def test_error_handling(self, mock_redis_client):
        """Test error handling in cache operations."""
        # Set up mock to raise exception
        mock_redis_client.get.side_effect = Exception("Redis connection error")

        # Create cache service with mock Redis
        cache_service = WeatherCacheService(mock_redis_client)

        # Test error handling - should return None
        result = await cache_service.get_weather("London", "2025-07-25")

        assert result is None
