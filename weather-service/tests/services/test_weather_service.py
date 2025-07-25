"""
Tests for the weather service module.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

from app.exceptions import RateLimitExceededException
from app.schemas.api_v1 import WeatherResponse
from app.schemas.api_v2 import WeatherResponseV2
from app.services.weather_service import WeatherService, ApiVersion


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for weather service."""
    weather_cache = AsyncMock()
    rate_limiter = AsyncMock()
    stats_tracker = AsyncMock()
    queue_manager = AsyncMock()

    return weather_cache, rate_limiter, stats_tracker, queue_manager


@pytest.fixture
def weather_service(mock_dependencies):
    """Create a UnifiedWeatherService instance with mocked dependencies."""
    weather_cache, rate_limiter, stats_tracker, queue_manager = mock_dependencies
    return WeatherService(weather_cache, rate_limiter, stats_tracker, queue_manager)


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return [
        {"hour": 0, "temperature": "18°C", "condition": "Clear"},
        {"hour": 1, "temperature": "17°C", "condition": "Clear"},
        {"hour": 2, "temperature": "16°C", "condition": "Cloudy"},
    ]


class TestWeatherServiceV1:
    """Test cases for WeatherService."""

    async def test_get_weather_cache_hit(self, weather_service, sample_weather_data):
        """Test getting weather when data is in cache."""
        weather_service.weather_cache.get_weather.return_value = {
            "weather": sample_weather_data
        }

        result = await weather_service.get_weather("London", ApiVersion.V1)

        assert isinstance(result, WeatherResponse)
        assert len(result.weather) == 3
        assert result.weather[0].temperature == "18"
        assert result.weather[0].condition == "Clear"

        weather_service.weather_cache.get_weather.assert_called_once_with(
            "London", date.today().isoformat()
        )
        weather_service.stats_tracker.increment_stats.assert_called_once_with("London")

    async def test_get_weather_cache_miss_api_success(
        self, weather_service, sample_weather_data
    ):
        """Test getting weather when cache misses but API call succeeds."""
        weather_service.weather_cache.get_weather.return_value = None
        weather_service.rate_limiter.consume_rate_limit_token.return_value = True

        with pytest.MonkeyPatch.context() as m:
            mock_api = AsyncMock()
            mock_api.fetch_weather.return_value = {"result": sample_weather_data}
            m.setattr("app.services.weather_service.dummy_weather_api", mock_api)

            result = await weather_service.get_weather("London", ApiVersion.V1)

            assert isinstance(result, WeatherResponse)
            assert len(result.weather) == 3
            assert result.weather[0].temperature == "18"

            weather_service.weather_cache.set_weather.assert_called_once()
            mock_api.fetch_weather.assert_called_once_with("London")

    async def test_get_weather_rate_limited_with_stale_data(
        self, weather_service, sample_weather_data
    ):
        """Test getting weather when rate limited but stale data exists."""
        weather_service.weather_cache.get_weather.return_value = None
        weather_service.rate_limiter.consume_rate_limit_token.return_value = False
        weather_service.weather_cache.get_stale_weather.return_value = {
            "weather": sample_weather_data
        }

        result = await weather_service.get_weather("London", ApiVersion.V1)

        assert isinstance(result, WeatherResponse)
        assert len(result.weather) == 3
        weather_service.weather_cache.get_stale_weather.assert_called_once()

    async def test_get_weather_rate_limited_no_data(self, weather_service):
        """Test getting weather when rate limited and no cached data exists."""
        weather_service.weather_cache.get_weather.return_value = None
        weather_service.rate_limiter.consume_rate_limit_token.return_value = False
        weather_service.weather_cache.get_stale_weather.return_value = None

        with pytest.raises(RateLimitExceededException):
            await weather_service.get_weather("London", ApiVersion.V1)

        weather_service.queue_manager.add_to_queue.assert_called_once_with(
            "London", priority=10
        )

    async def test_get_weather_api_failure_with_stale_data(
        self, weather_service, sample_weather_data
    ):
        """Test getting weather when API fails but stale data exists."""
        weather_service.weather_cache.get_weather.return_value = None
        weather_service.rate_limiter.consume_rate_limit_token.return_value = True
        weather_service.weather_cache.get_stale_weather.return_value = {
            "weather": sample_weather_data
        }

        with pytest.MonkeyPatch.context() as m:
            mock_api = AsyncMock()
            mock_api.fetch_weather.side_effect = Exception("API Error")
            m.setattr("app.services.weather_service.dummy_weather_api", mock_api)

            result = await weather_service.get_weather("London", ApiVersion.V1)

            assert isinstance(result, WeatherResponse)
            weather_service.weather_cache.get_stale_weather.assert_called_once()


class TestWeatherServiceV2:
    """Test cases for WeatherServiceV2."""

    async def test_get_weather_v2_response_format(
        self, weather_service, sample_weather_data
    ):
        """Test that V2 service returns proper response format."""
        weather_service.weather_cache.get_weather.return_value = {
            "weather": sample_weather_data
        }

        result = await weather_service.get_weather("London", ApiVersion.V2)

        assert isinstance(result, WeatherResponseV2)
        assert result.city == "London"
        assert result.date == date.today().isoformat()
        assert len(result.weather) == 3
        assert result.weather[0].temperature == "18"
        assert result.metadata.data_freshness == "fresh"
        assert result.metadata.source == "cache"
        assert isinstance(result.metadata.last_updated, datetime)

    async def test_get_weather_v2_with_warnings(
        self, weather_service, sample_weather_data
    ):
        """Test V2 response includes warnings for stale data."""
        weather_service.weather_cache.get_weather.return_value = None
        weather_service.rate_limiter.consume_rate_limit_token.return_value = False
        weather_service.weather_cache.get_stale_weather.return_value = {
            "weather": sample_weather_data
        }

        result = await weather_service.get_weather("London", ApiVersion.V2)

        assert isinstance(result, WeatherResponseV2)
        assert result.metadata.data_freshness == "stale"
        assert len(result.warnings) == 1
        assert "24 hours old" in result.warnings[0]

    async def test_temperature_format_preserved(
        self, weather_service, sample_weather_data
    ):
        """Test that temperature format with °C is preserved in both service versions."""

        weather_service.weather_cache.get_weather.return_value = {
            "weather": sample_weather_data
        }
        result_v1 = await weather_service.get_weather("London", ApiVersion.V1)
        assert result_v1.weather[0].temperature == "18"

        weather_service.weather_cache.get_weather.return_value = {
            "weather": sample_weather_data
        }
        result_v2 = await weather_service.get_weather("London", ApiVersion.V2)
        assert result_v2.weather[0].temperature == "18"
