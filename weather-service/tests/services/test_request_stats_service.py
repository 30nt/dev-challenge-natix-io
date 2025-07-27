"""
Tests for the request stats service module.
"""

from unittest.mock import AsyncMock

import pytest
import redis.asyncio as redis

from app.services.request_stats_service import RequestStatsService


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    return AsyncMock()


@pytest.fixture
def stats_service(mock_redis):
    """Create a RequestStatsService instance with mocked Redis."""
    return RequestStatsService(mock_redis)


class TestRequestStatsService:
    """Test cases for RequestStatsService."""

    async def test_increment_stats_success(self, stats_service, mock_redis):
        """Test successful stats increment."""
        mock_redis.incr.return_value = 1
        mock_redis.expire.return_value = True
        mock_redis.zincrby.return_value = 1.0

        await stats_service.increment_stats("London")

        mock_redis.incr.assert_called_once_with("weather:stats:london:request_count")
        assert mock_redis.expire.call_count == 2
        mock_redis.zincrby.assert_called_once_with("top_cities", 1, "london")

    async def test_increment_stats_connection_error(self, stats_service, mock_redis):
        """Test handling connection error in increment_stats."""
        mock_redis.incr.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await stats_service.increment_stats("London")

    async def test_increment_stats_timeout_error(self, stats_service, mock_redis):
        """Test handling timeout error in increment_stats."""
        mock_redis.incr.side_effect = redis.TimeoutError("Timeout")

        await stats_service.increment_stats("London")

        mock_redis.incr.assert_called_once()

    async def test_increment_stats_general_error(self, stats_service, mock_redis):
        """Test handling general error in increment_stats."""
        mock_redis.incr.side_effect = Exception("General error")

        await stats_service.increment_stats("London")

        mock_redis.incr.assert_called_once()

    async def test_get_top_cities_success(self, stats_service, mock_redis):
        """Test getting top cities by request count."""

        mock_redis.zrevrange.return_value = [
            (b"london", 100.0),
            (b"paris", 75.0),
            (b"berlin", 50.0),
        ]

        result = await stats_service.get_top_cities(count=3)

        assert len(result) == 3
        assert result[0] == ("london", 100)
        assert result[1] == ("paris", 75)
        assert result[2] == ("berlin", 50)

        mock_redis.zrevrange.assert_called_once_with(
            "top_cities", 0, 2, withscores=True
        )

    async def test_get_top_cities_string_cities(self, stats_service, mock_redis):
        """Test get_top_cities when cities are already strings."""
        mock_redis.zrevrange.return_value = [("london", 100.0), ("paris", 75.0)]

        result = await stats_service.get_top_cities(count=2)

        assert len(result) == 2
        assert result[0] == ("london", 100)
        assert result[1] == ("paris", 75)

    async def test_get_top_cities_default_count(self, stats_service, mock_redis):
        """Test get_top_cities with default count."""
        mock_redis.zrevrange.return_value = []

        await stats_service.get_top_cities()

        mock_redis.zrevrange.assert_called_once_with(
            "top_cities", 0, 49, withscores=True
        )

    async def test_get_top_cities_connection_error(self, stats_service, mock_redis):
        """Test handling connection error in get_top_cities."""
        mock_redis.zrevrange.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await stats_service.get_top_cities()

    async def test_get_top_cities_timeout_error(self, stats_service, mock_redis):
        """Test handling timeout error in get_top_cities."""
        mock_redis.zrevrange.side_effect = redis.TimeoutError("Timeout")

        result = await stats_service.get_top_cities()

        assert result == []

    async def test_get_top_cities_general_error(self, stats_service, mock_redis):
        """Test handling general error in get_top_cities."""
        mock_redis.zrevrange.side_effect = Exception("General error")

        result = await stats_service.get_top_cities()

        assert result == []

    async def test_get_city_stats_success(self, stats_service, mock_redis):
        """Test getting stats for a specific city."""
        mock_redis.zscore.return_value = 42.0

        result = await stats_service.get_city_stats("London")

        assert result == 42
        mock_redis.zscore.assert_called_once_with("top_cities", "london")

    async def test_get_city_stats_no_data(self, stats_service, mock_redis):
        """Test getting stats for city with no data."""
        mock_redis.zscore.return_value = None

        result = await stats_service.get_city_stats("London")

        assert result == 0

    async def test_get_city_stats_connection_error(self, stats_service, mock_redis):
        """Test handling connection error in get_city_stats."""
        mock_redis.zscore.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await stats_service.get_city_stats("London")

    async def test_get_city_stats_timeout_error(self, stats_service, mock_redis):
        """Test handling timeout error in get_city_stats."""
        mock_redis.zscore.side_effect = redis.TimeoutError("Timeout")

        result = await stats_service.get_city_stats("London")

        assert result == 0

    async def test_get_city_stats_general_error(self, stats_service, mock_redis):
        """Test handling general error in get_city_stats."""
        mock_redis.zscore.side_effect = Exception("General error")

        result = await stats_service.get_city_stats("London")

        assert result == 0

    def test_get_stats_key(self, stats_service):
        """Test stats key generation."""
        key = stats_service._get_stats_key("London")
        assert key == "weather:stats:london:request_count"

        key = stats_service._get_stats_key("LONDON")
        assert key == "weather:stats:london:request_count"
