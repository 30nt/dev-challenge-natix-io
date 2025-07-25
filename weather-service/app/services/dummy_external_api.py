"""
This module simulates an external API for testing purposes.
"""

import asyncio
import random
from datetime import datetime, UTC, timedelta
from typing import Dict, Any, List, Optional

from app.definitions.data_sources import WeatherCondition, WindDirections
from app.utils.circuit_breaker import circuit_breaker


class RateLimitTracker:
    """
    Simulates external API rate limiting (100 requests per hour).

    This tracker maintains request counts and enforces the limit
    to demonstrate how the application handles rate limiting.
    """

    def __init__(self, requests_per_hour: int = 100):
        self.requests_per_hour = requests_per_hour
        self.window_start: Optional[datetime] = None
        self.request_count = 0

    def reset_window_if_needed(self) -> None:
        """Reset the rate limit window if an hour has passed."""
        current_time = datetime.now(UTC)

        if self.window_start is None:
            self.window_start = current_time
            self.request_count = 0
            return

        if current_time - self.window_start >= timedelta(hours=1):
            self.window_start = current_time
            self.request_count = 0

    def can_make_request(self) -> bool:
        """Check if we can make a request within the rate limit."""
        self.reset_window_if_needed()
        return self.request_count < self.requests_per_hour

    def record_request(self) -> None:
        """Record a request against the rate limit."""
        self.reset_window_if_needed()
        self.request_count += 1

    def get_remaining_requests(self) -> int:
        """Get the number of remaining requests in current window."""
        self.reset_window_if_needed()
        return max(0, self.requests_per_hour - self.request_count)

    def get_reset_time(self) -> datetime:
        """Get when the rate limit window will reset."""
        if self.window_start is None:
            return datetime.now(UTC)
        return self.window_start + timedelta(hours=1)


class DummyWeatherAPI:
    """
    Mock weather API that generates realistic weather data.

    Used for development and testing without consuming real API rate limits.
    """

    CITY_WEATHER_PATTERNS = {
        "singapore": {
            "temp_range": (24, 32),
            "humidity_range": (70, 90),
            "conditions": [
                (WeatherCondition.RAINY, 0.3),
                (WeatherCondition.PARTLY_CLOUDY, 0.4),
                (WeatherCondition.CLOUDY, 0.2),
                (WeatherCondition.STORMY, 0.1),
            ],
        },
        "dubai": {
            "temp_range": (25, 45),
            "humidity_range": (30, 60),
            "conditions": [
                (WeatherCondition.CLEAR, 0.6),
                (WeatherCondition.PARTLY_CLOUDY, 0.3),
                (WeatherCondition.WINDY, 0.1),
            ],
        },
        "london": {
            "temp_range": (5, 25),
            "humidity_range": (60, 80),
            "conditions": [
                (WeatherCondition.CLOUDY, 0.3),
                (WeatherCondition.RAINY, 0.3),
                (WeatherCondition.PARTLY_CLOUDY, 0.2),
                (WeatherCondition.CLEAR, 0.1),
                (WeatherCondition.FOGGY, 0.1),
            ],
        },
        "new york": {
            "temp_range": (-5, 35),
            "humidity_range": (40, 70),
            "conditions": [
                (WeatherCondition.CLEAR, 0.3),
                (WeatherCondition.PARTLY_CLOUDY, 0.3),
                (WeatherCondition.CLOUDY, 0.2),
                (WeatherCondition.RAINY, 0.1),
                (WeatherCondition.SNOWY, 0.1),
            ],
        },
        "toronto": {
            "temp_range": (-20, 30),
            "humidity_range": (50, 75),
            "conditions": [
                (WeatherCondition.SNOWY, 0.3),
                (WeatherCondition.CLOUDY, 0.3),
                (WeatherCondition.CLEAR, 0.2),
                (WeatherCondition.PARTLY_CLOUDY, 0.2),
            ],
        },
        "default": {
            "temp_range": (10, 30),
            "humidity_range": (40, 80),
            "conditions": [
                (WeatherCondition.CLEAR, 0.25),
                (WeatherCondition.PARTLY_CLOUDY, 0.25),
                (WeatherCondition.CLOUDY, 0.25),
                (WeatherCondition.RAINY, 0.25),
            ],
        },
    }

    def __init__(self):
        """Initialize the dummy weather API with rate limiting."""
        self.request_count = 0
        self.rate_limiter = RateLimitTracker(requests_per_hour=100)

    def get_weather_pattern(self, city: str) -> Dict[str, Any]:
        """Get weather pattern for a city."""
        city_lower = city.lower()

        for pattern_city, pattern in self.CITY_WEATHER_PATTERNS.items():
            if pattern_city in city_lower:
                return pattern

        return self.CITY_WEATHER_PATTERNS["default"]

    def generate_temperature_curve(self, base_temp: int, hour: int) -> int:
        """Generate realistic temperature curve throughout the day."""

        hour_offset = (hour - 6) % 24

        if hour_offset <= 8:
            variation = int(5 * (hour_offset / 8))
        elif hour_offset <= 16:
            variation = int(5 * (1 - (hour_offset - 8) / 8))
        else:
            variation = -2

        return base_temp + variation

    def select_weather_condition(self, conditions: List[tuple]) -> str:
        """Select a weather condition based on probability weights."""
        rand = random.random()
        cumulative = 0.0

        for condition, probability in conditions:
            cumulative += probability
            if rand <= cumulative:
                return condition.value

        return conditions[0][0].value

    def _generate_hourly_data(
        self, hour: int, base_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate weather data for a specific hour.
        """
        temperature = self.generate_temperature_curve(base_data["base_temp"], hour)
        humidity = self._calculate_humidity(base_data["base_humidity"])
        wind_speed = self._calculate_wind_speed(base_data["dominant_condition"])
        condition = self._select_hourly_condition(
            base_data["dominant_condition"], base_data["pattern"]
        )
        feels_like = self._calculate_feels_like(temperature, wind_speed, humidity)

        return {
            "hour": hour,
            "temperature": f"{temperature}°C",
            "condition": condition,
            "feels_like": feels_like,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "wind_direction": random.choice(list(WindDirections)).value,
            "pressure": random.randint(1000, 1020),
            "visibility": random.randint(5, 20),
            "uv_index": (
                random.randint(0, 11)
                if condition == WeatherCondition.CLEAR.value
                else 0
            ),
        }

    def _calculate_humidity(self, base_humidity: int) -> int:
        """
        Calculate humidity for an hour.
        """
        humidity = base_humidity + random.randint(-5, 5)
        return max(0, min(100, humidity))

    def _calculate_wind_speed(self, dominant_condition: str) -> int:
        """
        Calculate wind speed based on conditions.
        """
        if dominant_condition in [
            WeatherCondition.STORMY.value,
            WeatherCondition.WINDY.value,
        ]:
            return random.randint(20, 40)
        return random.randint(5, 25)

    def _select_hourly_condition(self, dominant_condition: str, pattern: Dict) -> str:
        """
        Select weather condition for an hour.
        """
        if random.random() < 0.8:
            return dominant_condition
        return self.select_weather_condition(pattern["conditions"])

    def _calculate_feels_like(
        self, temperature: int, wind_speed: int, humidity: int
    ) -> int:
        """
        Calculate feels-like temperature.
        """
        feels_like = temperature
        if wind_speed > 20:
            feels_like -= 3
        if humidity > 80:
            feels_like += 2
        return feels_like

    def generate_mock_weather_data(self, city: str) -> Dict[str, Any]:
        """
        Generate realistic mock weather data for a city.
        """
        self.request_count += 1
        pattern = self.get_weather_pattern(city)

        base_data = {
            "base_temp": random.randint(*pattern["temp_range"]),
            "base_humidity": random.randint(*pattern["humidity_range"]),
            "dominant_condition": self.select_weather_condition(pattern["conditions"]),
            "pattern": pattern,
        }

        result = [self._generate_hourly_data(hour, base_data) for hour in range(24)]

        return {
            "result": result,
            "metadata": {
                "city": city,
                "generated_at": datetime.now(UTC).isoformat(),
                "api_version": "dummy-1.0",
                "request_count": self.request_count,
            },
        }

    @circuit_breaker(
        failure_threshold=3,
        recovery_timeout=30,
        expected_exception=ValueError,
        name="weather_api",
    )
    async def fetch_weather(self, city: str) -> Dict[str, Any]:
        """
        Async method to fetch weather data with rate limiting.

        This method simulates real external API behavior including:
        - Rate limiting (100 requests per hour)
        - Network delays
        - Occasional failures
        """

        if not self.rate_limiter.can_make_request():
            remaining_time = self.rate_limiter.get_reset_time() - datetime.now(UTC)
            remaining_seconds = int(remaining_time.total_seconds())

            raise ValueError(
                f"Rate limit exceeded. 100 requests per hour limit reached. "
                f"Try again in {remaining_seconds} seconds."
            )

        self.rate_limiter.record_request()

        await asyncio.sleep(random.uniform(0.1, 0.3))

        if random.random() < 0.05:
            raise ValueError("Dummy API simulated server error")

        return self.generate_mock_weather_data(city)

    def get_rate_limit_info(self) -> Dict[str, Any]:
        """
        Get current rate limit information.
        """
        return {
            "requests_per_hour": self.rate_limiter.requests_per_hour,
            "requests_made": self.rate_limiter.request_count,
            "requests_remaining": self.rate_limiter.get_remaining_requests(),
            "window_start": (
                self.rate_limiter.window_start.isoformat()
                if self.rate_limiter.window_start
                else None
            ),
            "window_reset": self.rate_limiter.get_reset_time().isoformat(),
            "can_make_request": self.rate_limiter.can_make_request(),
        }


dummy_weather_api = DummyWeatherAPI()
