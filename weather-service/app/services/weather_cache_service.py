"""
Weather-specific caching service.
"""

import json
from datetime import datetime, UTC
from typing import Optional, Dict, Any

import redis.asyncio as redis

from app.config import get_settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class WeatherCacheService:
    """
    Service responsible for weather data caching operations.

    Handles primary cache, stale data fallback, and metadata management.
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize weather cache service.

        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client

    def _get_weather_key(self, city: str, date: str) -> str:
        """
        Generate cache key for weather data.
        """
        return f"weather:{city.lower()}:{date}"

    def _get_meta_key(self, city: str) -> str:
        """
        Generate cache key for metadata.
        """
        return f"weather:meta:{city.lower()}:last_update"

    async def get_weather(self, city: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Get weather data from cache.
        """
        try:
            key = self._get_weather_key(city, date)
            data = await self.redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except redis.ConnectionError:
            logger.error("Redis connection failed while getting weather for %s", city)
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while getting weather for %s", city)
            return None
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in cache for %s: %s", city, e)
            return None
        except Exception as e:
            logger.error("Unexpected error getting weather for %s: %s", city, e)
            return None

    async def set_weather(
        self,
        city: str,
        date: str,
        weather_data: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ):
        """
        Set weather data in cache with TTL.
        """
        try:
            key = self._get_weather_key(city, date)
            ttl = ttl_seconds or settings.redis_cache_ttl

            await self.redis_client.setex(key, ttl, json.dumps(weather_data))

            # Set metadata
            meta_key = self._get_meta_key(city)
            await self.redis_client.setex(
                meta_key, settings.redis_stale_ttl, datetime.now(UTC).isoformat()
            )

            logger.info("Cached weather data for %s with TTL %ss", city, ttl)

        except redis.ConnectionError:
            logger.error("Redis connection failed while setting weather for %s", city)
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while setting weather for %s", city)
        except Exception as e:
            logger.error("Unexpected error setting weather for %s: %s", city, e)

    async def get_stale_weather(self, city: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Get stale weather data from cache as fallback.

        Uses a separate stale key to avoid confusion with primary cache.
        """
        try:
            key = self._get_weather_key(city, date)
            stale_key = f"{key}:stale"

            # First check if we have dedicated stale data
            data = await self.redis_client.get(stale_key)
            if data:
                return json.loads(data)

            # If no stale data, check if primary data exists and copy it
            data = await self.redis_client.get(key)
            if data:
                # Store as stale data for future use
                await self.redis_client.setex(stale_key, settings.redis_stale_ttl, data)
                return json.loads(data)

            return None

        except redis.ConnectionError:
            logger.error(
                "Redis connection failed while getting stale weather for %s", city
            )
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while getting stale weather for %s", city)
            return None
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in stale cache for %s: %s", city, e)
            return None
        except Exception as e:
            logger.error("Unexpected error getting stale weather for %s: %s", city, e)
            return None
