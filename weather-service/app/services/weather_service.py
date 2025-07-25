from abc import ABC, abstractmethod
from datetime import datetime, date, UTC
from typing import Optional, List, Union

from app.config import get_settings
from app.exceptions import RateLimitExceededException
from app.schemas.api_v1 import WeatherResponse, HourlyWeather
from app.schemas.api_v2 import WeatherResponseV2, WeatherMetadata, HourlyWeatherV2
from app.services.cache_service import CacheService
from app.services.dummy_external_api import dummy_weather_api
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class BaseWeatherService(ABC):
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service

    async def get_weather(self, city: str) -> Union[WeatherResponse, WeatherResponseV2]:
        today = date.today().isoformat()

        cached_data = await self.cache_service.get_weather(city, today)
        if cached_data:
            logger.info(f"Cache hit for {city}")
            return self._build_response(
                city=city,
                date=today,
                weather_data=cached_data["weather"],
                source="cache",
                freshness="fresh",
            )

        logger.info(f"Cache miss for {city}")

        if await self.cache_service.consume_rate_limit_token():
            try:
                logger.info(f"Fetching weather from external API for {city}")
                external_data = await dummy_weather_api.fetch_weather(city)

                if external_data:
                    await self.cache_service.set_weather(
                        city=city, date=today, weather_data=external_data
                    )

                    return self._build_response(
                        city=city,
                        date=today,
                        weather_data=external_data["weather"],
                        source="api",
                        freshness="fresh",
                    )
            except Exception as e:
                logger.error(f"Failed to fetch weather from external API: {e}")

        logger.warning(
            f"Rate limited or API failed, checking for stale data for {city}"
        )
        stale_data = await self.cache_service.get_stale_weather(city, today)

        if stale_data:
            return self._build_response(
                city=city,
                date=today,
                weather_data=stale_data["weather"],
                source="cache",
                freshness="stale",
                warning="Data might be up to 24 hours old due to rate limiting",
            )

        await self.cache_service.add_to_queue(city, priority=10)

        raise RateLimitExceededException(
            "Weather data unavailable. Request has been queued."
        )

    @abstractmethod
    def _build_response(
        self,
        city: str,
        date: str,
        weather_data: List[dict],
        source: str,
        freshness: str,
        warning: Optional[str] = None,
    ) -> Union[WeatherResponse, WeatherResponseV2]:
        pass


class WeatherService(BaseWeatherService):
    def _build_response(
        self,
        city: str,
        date: str,
        weather_data: List[dict],
        source: str,
        freshness: str,
        warning: Optional[str] = None,
    ) -> WeatherResponse:
        hourly_weather = [HourlyWeather(**hour_data) for hour_data in weather_data]

        return WeatherResponse(weather=hourly_weather)


class WeatherServiceV2(BaseWeatherService):
    def _build_response(
        self,
        city: str,
        date: str,
        weather_data: List[dict],
        source: str,
        freshness: str,
        warning: Optional[str] = None,
    ) -> WeatherResponseV2:
        hourly_weather = [HourlyWeatherV2(**hour_data) for hour_data in weather_data]

        metadata = WeatherMetadata(
            last_updated=datetime.now(UTC), data_freshness=freshness, source=source
        )

        warnings = [warning] if warning else []

        return WeatherResponseV2(
            city=city,
            date=date,
            weather=hourly_weather,
            metadata=metadata,
            warnings=warnings,
        )
