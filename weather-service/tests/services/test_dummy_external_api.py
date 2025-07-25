"""
Tests for the dummy external API module.
"""

from datetime import datetime, UTC, timedelta
from unittest.mock import patch

import pytest

from app.definitions.data_sources import WeatherCondition, WindDirections
from app.services.dummy_external_api import DummyWeatherAPI, RateLimitTracker


class TestRateLimitTracker:
    """Test cases for RateLimitTracker."""

    def test_initialization(self):
        """Test rate limit tracker initialization."""
        tracker = RateLimitTracker(requests_per_hour=50)

        assert tracker.requests_per_hour == 50
        assert tracker.window_start is None
        assert tracker.request_count == 0

    def test_can_make_request_first_time(self):
        """Test first request is allowed."""
        tracker = RateLimitTracker()

        assert tracker.can_make_request() is True
        assert tracker.window_start is not None
        assert tracker.request_count == 0

    def test_record_request(self):
        """Test recording requests."""
        tracker = RateLimitTracker()

        tracker.can_make_request()
        tracker.record_request()
        assert tracker.request_count == 1

        tracker.record_request()
        assert tracker.request_count == 2

    def test_rate_limit_enforcement(self):
        """Test that rate limit is enforced."""
        tracker = RateLimitTracker(requests_per_hour=2)

        assert tracker.can_make_request() is True
        tracker.record_request()
        assert tracker.can_make_request() is True
        tracker.record_request()

        assert tracker.can_make_request() is False
        assert tracker.get_remaining_requests() == 0

    def test_window_reset(self):
        """Test rate limit window reset after an hour."""
        tracker = RateLimitTracker(requests_per_hour=1)

        assert tracker.can_make_request() is True
        tracker.record_request()
        assert tracker.can_make_request() is False

        original_window = tracker.window_start
        tracker.window_start = datetime.now(UTC) - timedelta(hours=1, minutes=1)

        assert tracker.can_make_request() is True
        assert tracker.request_count == 0
        assert tracker.window_start > original_window

    def test_get_remaining_requests(self):
        """Test getting remaining requests."""
        tracker = RateLimitTracker(requests_per_hour=100)

        assert tracker.get_remaining_requests() == 100

        tracker.can_make_request()
        tracker.record_request()
        assert tracker.get_remaining_requests() == 99

        for _ in range(99):
            tracker.record_request()
        assert tracker.get_remaining_requests() == 0

    def test_get_reset_time(self):
        """Test getting reset time."""
        tracker = RateLimitTracker()

        reset_time_before = tracker.get_reset_time()
        assert isinstance(reset_time_before, datetime)

        tracker.can_make_request()
        reset_time = tracker.get_reset_time()
        assert reset_time == tracker.window_start + timedelta(hours=1)


class TestDummyWeatherAPI:
    """Test cases for DummyWeatherAPI."""

    def test_initialization(self):
        """Test API initialization."""
        api = DummyWeatherAPI()

        assert api.request_count == 0
        assert isinstance(api.rate_limiter, RateLimitTracker)
        assert api.rate_limiter.requests_per_hour == 100

    def test_get_weather_pattern(self):
        """Test weather pattern selection for cities."""
        api = DummyWeatherAPI()

        singapore_pattern = api.get_weather_pattern("Singapore")
        assert singapore_pattern["temp_range"] == (24, 32)
        assert singapore_pattern["humidity_range"] == (70, 90)

        london_pattern = api.get_weather_pattern("London")
        assert london_pattern["temp_range"] == (5, 25)

        unknown_pattern = api.get_weather_pattern("Unknown City")
        assert unknown_pattern == api.CITY_WEATHER_PATTERNS["default"]

    def test_generate_temperature_curve(self):
        """Test temperature curve generation."""
        api = DummyWeatherAPI()
        base_temp = 20

        temp_6am = api.generate_temperature_curve(base_temp, 6)
        temp_2pm = api.generate_temperature_curve(base_temp, 14)
        temp_10pm = api.generate_temperature_curve(base_temp, 22)

        assert temp_6am == base_temp
        assert temp_2pm > temp_6am
        assert temp_10pm < temp_2pm

    def test_select_weather_condition(self):
        """Test weather condition selection."""
        api = DummyWeatherAPI()

        conditions = [(WeatherCondition.CLEAR, 1.0)]

        for _ in range(10):
            assert (
                api.select_weather_condition(conditions) == WeatherCondition.CLEAR.value
            )

    def test_generate_mock_weather_data(self):
        """Test mock weather data generation."""
        api = DummyWeatherAPI()

        data = api.generate_mock_weather_data("London")

        assert "result" in data
        assert "metadata" in data
        assert len(data["result"]) == 24

        hour_data = data["result"][0]
        assert hour_data["hour"] == 0
        assert "°C" in hour_data["temperature"]
        assert "condition" in hour_data
        assert "humidity" in hour_data
        assert "wind_speed" in hour_data

        assert data["metadata"]["city"] == "London"
        assert data["metadata"]["api_version"] == "dummy-1.0"
        assert data["metadata"]["request_count"] == 1

    @pytest.mark.asyncio
    async def test_fetch_weather_success(self):
        """Test successful weather fetch."""
        api = DummyWeatherAPI()

        with patch("random.random", return_value=0.99):
            result = await api.fetch_weather("Paris")

        assert "result" in result
        assert len(result["result"]) == 24
        assert api.rate_limiter.request_count == 1

    @pytest.mark.asyncio
    async def test_fetch_weather_rate_limit(self):
        """Test rate limiting behavior."""
        api = DummyWeatherAPI()

        for _ in range(100):
            api.rate_limiter.record_request()

        with pytest.raises(ValueError, match="Rate limit exceeded"):
            await api.fetch_weather("London")

    @pytest.mark.asyncio
    async def test_fetch_weather_simulated_failure(self):
        """Test simulated API failure."""
        api = DummyWeatherAPI()

        with patch("random.random", return_value=0.01):
            with pytest.raises(ValueError, match="simulated server error"):
                await api.fetch_weather("London")

    @pytest.mark.asyncio
    async def test_fetch_weather_with_circuit_breaker(self):
        """Test that fetch_weather uses circuit breaker."""
        api = DummyWeatherAPI()

        assert hasattr(api, "circuit_breaker")
        assert api.circuit_breaker.name == "weather_api"
        assert api.circuit_breaker.failure_threshold == 3
        assert api.circuit_breaker.recovery_timeout == 30

    def test_get_rate_limit_info(self):
        """Test getting rate limit information."""
        api = DummyWeatherAPI()

        api.rate_limiter.can_make_request()
        api.rate_limiter.record_request()
        api.rate_limiter.record_request()

        info = api.get_rate_limit_info()

        assert info["requests_per_hour"] == 100
        assert info["requests_made"] == 2
        assert info["requests_remaining"] == 98
        assert info["can_make_request"] is True
        assert "window_start" in info
        assert "window_reset" in info

    def test_hourly_data_structure(self):
        """Test that hourly data has all required fields."""
        api = DummyWeatherAPI()

        base_data = {
            "base_temp": 20,
            "base_humidity": 60,
            "dominant_condition": WeatherCondition.CLEAR.value,
            "pattern": api.CITY_WEATHER_PATTERNS["default"],
        }

        hour_data = api._generate_hourly_data(12, base_data)

        required_fields = [
            "hour",
            "temperature",
            "condition",
            "feels_like",
            "humidity",
            "wind_speed",
            "wind_direction",
            "pressure",
            "visibility",
            "uv_index",
        ]

        for field in required_fields:
            assert field in hour_data

        assert hour_data["hour"] == 12
        assert "°C" in hour_data["temperature"]
        assert isinstance(hour_data["humidity"], int)
        assert 0 <= hour_data["humidity"] <= 100
        assert hour_data["wind_direction"] in [d.value for d in WindDirections]
        assert 1000 <= hour_data["pressure"] <= 1020
        assert 5 <= hour_data["visibility"] <= 20

    def test_temperature_format_consistency(self):
        """Test that temperature always includes °C."""
        api = DummyWeatherAPI()

        data = api.generate_mock_weather_data("TestCity")

        for hour_data in data["result"]:
            assert "°C" in hour_data["temperature"]
            temp_value = hour_data["temperature"].replace("°C", "").strip()
            assert temp_value.isdigit() or (
                temp_value.startswith("-") and temp_value[1:].isdigit()
            )
