from typing import Optional, List
from datetime import datetime, date, UTC
from app.models.weather import WeatherResponse, HourlyWeather, WeatherMetadata
from app.services.cache_service import CacheService
from app.services.external_api import weather_api_client
from app.config import get_settings
from app.utils.logger import setup_logger
from app.exceptions import RateLimitExceededException

logger = setup_logger(__name__)
settings = get_settings()


class WeatherService:
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
    
    async def get_weather(self, city: str) -> WeatherResponse:
        today = date.today().isoformat()
        
        cached_data = await self.cache_service.get_weather(city, today)
        if cached_data:
            logger.info(f"Cache hit for {city}")
            return self._build_response(
                city=city,
                date=today,
                weather_data=cached_data["weather"],
                source="cache",
                freshness="fresh"
            )
        
        logger.info(f"Cache miss for {city}")
        
        if await self.cache_service.consume_rate_limit_token():
            try:
                logger.info(f"Fetching weather from external API for {city}")
                external_data = await weather_api_client.fetch_weather(city)
                
                if external_data:
                    await self.cache_service.set_weather(
                        city=city,
                        date=today,
                        weather_data=external_data
                    )
                    
                    return self._build_response(
                        city=city,
                        date=today,
                        weather_data=external_data["weather"],
                        source="api",
                        freshness="fresh"
                    )
            except Exception as e:
                logger.error(f"Failed to fetch weather from external API: {e}")
        
        logger.warning(f"Rate limited or API failed, checking for stale data for {city}")
        stale_data = await self.cache_service.get_stale_weather(city, today)
        
        if stale_data:
            return self._build_response(
                city=city,
                date=today,
                weather_data=stale_data["weather"],
                source="cache",
                freshness="stale",
                warning="Data might be up to 24 hours old due to rate limiting"
            )
        
        await self.cache_service.add_to_queue(city, priority=10)
        
        raise RateLimitExceededException(
            "Weather data unavailable. Request has been queued."
        )
    
    def _build_response(
        self,
        city: str,
        date: str,
        weather_data: List[dict],
        source: str,
        freshness: str,
        warning: Optional[str] = None
    ) -> WeatherResponse:
        hourly_weather = [
            HourlyWeather(**hour_data)
            for hour_data in weather_data
        ]
        
        metadata = WeatherMetadata(
            last_updated=datetime.now(UTC),
            data_freshness=freshness,
            cache_ttl_seconds=settings.redis_cache_ttl,
            source=source
        )
        
        warnings = [warning] if warning else []
        
        return WeatherResponse(
            city=city,
            date=date,
            weather=hourly_weather,
            metadata=metadata,
            warnings=warnings
        )