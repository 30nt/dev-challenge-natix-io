"""
This module provides weather-related services.
"""

from datetime import datetime, date, UTC
from typing import Optional, List, Union

from app.config import get_settings
from app.definitions.data_sources import ApiVersion
from app.exceptions import RateLimitExceededException
from app.schemas.api_v1 import WeatherResponse, HourlyWeather
from app.schemas.api_v2 import WeatherResponseV2, WeatherMetadata, HourlyWeatherV2
from app.services.dummy_external_api import dummy_weather_api
from app.services.queue_service import QueueService
from app.services.rate_limit_service import RateLimitService
from app.services.request_stats_service import RequestStatsService
from app.services.weather_cache_service import WeatherCacheService
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class WeatherService:
    """
    Unified weather service that handles both v1 and v2 API responses.
    """

    def __init__(
        self,
        weather_cache: WeatherCacheService,
        rate_limiter: RateLimitService,
        stats_tracker: RequestStatsService,
        queue_manager: QueueService,
    ):
        """
        Initialize weather service with direct service dependencies.
        """
        self.weather_cache = weather_cache
        self.rate_limiter = rate_limiter
        self.stats_tracker = stats_tracker
        self.queue_manager = queue_manager

    @staticmethod
    def _strip_temperature_units(weather_data: List[dict]) -> List[dict]:
        """
        Strip temperature units (°C) from weather data.
        """
        cleaned_data = []
        for hour_data in weather_data:
            cleaned_hour = hour_data.copy()
            if "temperature" in cleaned_hour and isinstance(
                cleaned_hour["temperature"], str
            ):
                cleaned_hour["temperature"] = (
                    cleaned_hour["temperature"].replace("°C", "").strip()
                )
            cleaned_data.append(cleaned_hour)
        return cleaned_data

    async def get_weather(
        self, city: str, version: ApiVersion = ApiVersion.V1
    ) -> Union[WeatherResponse, WeatherResponseV2]:
        """
        Get weather data for a city.
        """
        today_date = date.today().isoformat()

        cached_data = await self.weather_cache.get_weather(city, today_date)
        if cached_data:
            logger.info(
                "Cache hit",
                extra={
                    "city": city,
                    "event": "cache_hit",
                    "source": "redis",
                    "date": today_date,
                },
            )
            await self.stats_tracker.increment_stats(city)
            return self._build_response(
                city=city,
                date_str=today_date,
                weather_data=cached_data["weather"],
                source="cache",
                freshness="fresh",
                version=version,
            )

        logger.info(
            "Cache miss",
            extra={"city": city, "event": "cache_miss", "date": today_date},
        )

        if await self.rate_limiter.consume_rate_limit_token():
            try:
                logger.info(
                    "Fetching weather from external API",
                    extra={"city": city, "event": "api_call", "api": "weather"},
                )
                external_data = await dummy_weather_api.fetch_weather(city)

                if external_data:
                    await self.weather_cache.set_weather(
                        city=city, date=today_date, weather_data=external_data
                    )

                    return self._build_response(
                        city=city,
                        date_str=today_date,
                        weather_data=external_data["result"],
                        source="api",
                        freshness="fresh",
                        version=version,
                    )
            except Exception as e:
                logger.error(
                    "Failed to fetch weather from external API",
                    extra={
                        "city": city,
                        "event": "api_error",
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

        logger.warning(
            "Rate limited or API failed, checking for stale data",
            extra={
                "city": city,
                "event": "fallback_stale",
                "reason": "rate_limit_or_api_failure",
            },
        )
        stale_data = await self.weather_cache.get_stale_weather(city, today_date)

        if stale_data:
            return self._build_response(
                city=city,
                date_str=today_date,
                weather_data=stale_data["weather"],
                source="cache",
                freshness="stale",
                warning="Data might be up to 24 hours old due to rate limiting",
                version=version,
            )

        await self.queue_manager.add_to_queue(city, priority=10)

        raise RateLimitExceededException(
            "Weather data unavailable. Request has been queued."
        )

    def _build_response(
        self,
        city: str,
        date_str: str,
        weather_data: List[dict],
        source: str,
        freshness: str,
        version: ApiVersion,
        warning: Optional[str] = None,
    ) -> Union[WeatherResponse, WeatherResponseV2]:
        """
        Build response object from weather data based on API version.
        """
        cleaned_data = self._strip_temperature_units(weather_data)

        if version == ApiVersion.V1:
            hourly_weather = [HourlyWeather(**hour_data) for hour_data in cleaned_data]
            return WeatherResponse(weather=hourly_weather)

        hourly_weather = [HourlyWeatherV2(**hour_data) for hour_data in cleaned_data]
        metadata = WeatherMetadata(
            last_updated=datetime.now(UTC), data_freshness=freshness, source=source
        )
        warnings = [warning] if warning else []
        return WeatherResponseV2(
            city=city,
            date=date_str,
            weather=hourly_weather,
            metadata=metadata,
            warnings=warnings,
        )
