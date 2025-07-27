"""
Weather-specific caching service.
"""

import json
from datetime import datetime, UTC
from typing import Optional, Dict, Any

import redis.asyncio as redis

from app.config import get_settings
from app.utils.logger import setup_logger
from app.utils.resilience import redis_retry, with_fallback, fallback_cache

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

    async def _get_weather_fallback(
        self, city: str, date: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback method for retrieving weather data when Redis is unavailable.

        This method is only called after all Redis retry attempts have failed.
        It serves as a last-resort mechanism to maintain service availability
        during Redis outages by using a limited in-memory LRU cache.

        Args:
            city: City name to retrieve weather for
            date: Date string for the weather data

        Returns:
            Weather data dictionary if found in fallback cache, None otherwise
        """
        key = self._get_weather_key(city, date)
        cached_json = fallback_cache.get(key)
        if cached_json:
            try:
                return json.loads(cached_json)
            except json.JSONDecodeError:
                return None
        return None

    @redis_retry(use_fallback=True)
    @with_fallback("_get_weather_fallback")
    async def get_weather(self, city: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve weather data from Redis cache with automatic retry and fallback.

        Behavior:
        1. Attempts to fetch data from Redis cache
        2. If Redis connection fails, automatically retries with exponential backoff
        3. After all retries are exhausted, falls back to in-memory cache
        4. Returns None if data is not found in any cache

        The fallback mechanism ensures service continuity during Redis outages,
        but Redis remains the primary cache for all normal operations.

        Args:
            city: City name to retrieve weather for
            date: Date in ISO format (YYYY-MM-DD)

        Returns:
            Dictionary containing weather data if found, None otherwise

        Raises:
            redis.ConnectionError: Re-raised after retry attempts for connection issues
            redis.TimeoutError: Re-raised after retry attempts for timeout issues
        """
        try:
            key = self._get_weather_key(city, date)
            data = await self.redis_client.get(key)

            if data:
                return json.loads(data)
            return None

        except json.JSONDecodeError as e:
            logger.error(
                "Invalid JSON in cache",
                extra={
                    "city": city,
                    "event": "cache_json_error",
                    "error": str(e),
                    "key": key,
                },
            )
            return None
        except Exception as e:
            if isinstance(e, (redis.ConnectionError, redis.TimeoutError)):
                raise
            logger.error(
                "Unexpected error getting weather",
                extra={
                    "city": city,
                    "event": "cache_get_error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return None

    async def _set_weather_fallback(
        self,
        city: str,
        date: str,
        weather_data: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ):
        """
        Fallback method for storing weather data when Redis is unavailable.

        This method is invoked only when Redis is completely unreachable after
        all retry attempts. It stores data in a limited-capacity in-memory cache
        to ensure that critical weather data can still be saved during outages.

        Note: The in-memory cache has limited capacity (200 entries) and uses
        LRU eviction when full. This is intentional as it's meant only for
        emergency use during Redis outages.

        Args:
            city: City name for the weather data
            date: Date string for the weather data
            weather_data: Weather information to cache
            ttl_seconds: Time-to-live in seconds (uses default if not specified)
        """
        key = self._get_weather_key(city, date)
        ttl = ttl_seconds or settings.redis_cache_ttl
        fallback_cache.set(key, json.dumps(weather_data), ttl_seconds=ttl)
        logger.info(
            "Stored weather data in fallback cache",
            extra={"city": city, "event": "fallback_cache_set", "key": key, "ttl": ttl},
        )

    @redis_retry(use_fallback=True)
    @with_fallback("_set_weather_fallback")
    async def set_weather(
        self,
        city: str,
        date: str,
        weather_data: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ):
        """
        Store weather data in Redis cache with automatic retry and fallback.

        Behavior:
        1. Serializes weather data to JSON format
        2. Stores data in Redis with specified TTL
        3. Updates metadata key with last update timestamp
        4. If Redis fails, retries with exponential backoff
        5. Falls back to in-memory storage only if Redis is completely unavailable

        This method prioritizes Redis storage for high-performance caching.
        The fallback is used only during complete Redis outages to maintain
        write availability.

        Args:
            city: City name for the weather data
            date: Date in ISO format (YYYY-MM-DD)
            weather_data: Dictionary containing weather information
            ttl_seconds: Optional TTL in seconds (defaults to config value)

        Note:
            Both the weather data and metadata are stored atomically when possible.
            The metadata key has a longer TTL for stale data scenarios.
        """
        key = self._get_weather_key(city, date)
        ttl = ttl_seconds or settings.redis_cache_ttl
        data_json = json.dumps(weather_data)

        await self.redis_client.setex(key, ttl, data_json)

        meta_key = self._get_meta_key(city)
        await self.redis_client.setex(
            meta_key, settings.redis_stale_ttl, datetime.now(UTC).isoformat()
        )

        logger.info(
            "Cached weather data",
            extra={
                "city": city,
                "event": "cache_set",
                "ttl_seconds": ttl,
                "date": date,
                "has_metadata": True,
            },
        )

    async def _get_stale_weather_fallback(
        self, city: str, date: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback method for retrieving stale weather data when Redis is unavailable.

        This method searches for any available weather data in the in-memory cache,
        checking both regular and stale-specific keys. It's designed to provide
        the best available data during Redis outages, even if that data is outdated.

        Search order:
        1. Check for data with regular key (might be recently cached)
        2. Check for data with stale-specific key

        Args:
            city: City name to search for
            date: Date string to search for

        Returns:
            Any available weather data from fallback cache, None if nothing found
        """
        for suffix in ["", ":stale"]:
            key = self._get_weather_key(city, date) + suffix
            cached_json = fallback_cache.get(key)
            if cached_json:
                try:
                    return json.loads(cached_json)
                except json.JSONDecodeError:
                    continue
        return None

    @redis_retry(use_fallback=True)
    @with_fallback("_get_stale_weather_fallback")
    async def get_stale_weather(self, city: str, date: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve stale weather data with automatic retry and fallback support.

        This method is specifically designed for scenarios where fresh data is
        unavailable (e.g., rate limits exceeded, external API down). It provides
        a two-tier approach to finding the best available historical data.

        Behavior:
        1. First checks for data explicitly marked as stale (with :stale suffix)
        2. If not found, checks regular cache keys and promotes them to stale
        3. Implements full retry logic for Redis failures
        4. Falls back to in-memory cache during Redis outages

        The stale data mechanism ensures users receive weather information even
        when fresh updates cannot be obtained, with appropriate warnings about
        data freshness handled at higher layers.

        Args:
            city: City name to search for
            date: Date in ISO format (YYYY-MM-DD)

        Returns:
            Dictionary containing weather data (possibly outdated), None if not found

        Note:
            When regular data is found and promoted to stale, it's copied with
            an extended TTL to ensure availability for future stale requests.
        """
        try:
            key = self._get_weather_key(city, date)
            stale_key = f"{key}:stale"

            data = await self.redis_client.get(stale_key)
            if data:
                return json.loads(data)

            data = await self.redis_client.get(key)
            if data:
                await self.redis_client.setex(stale_key, settings.redis_stale_ttl, data)
                return json.loads(data)

            return None

        except json.JSONDecodeError as e:
            logger.error(
                "Invalid JSON in stale cache",
                extra={
                    "city": city,
                    "event": "stale_cache_json_error",
                    "error": str(e),
                    "key": stale_key,
                },
            )
            return None
        except Exception as e:
            if isinstance(e, (redis.ConnectionError, redis.TimeoutError)):
                raise
            logger.error(
                "Unexpected error getting stale weather",
                extra={
                    "city": city,
                    "event": "stale_cache_get_error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return None
