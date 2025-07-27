"""
FastAPI dependency injection providers.

This module provides dependency functions that leverage FastAPI's
built-in dependency injection system for better testability and
reduced coupling compared to global singleton containers.
"""

from typing import AsyncGenerator

import redis.asyncio as redis
from fastapi import Depends

from app.config import get_settings
from app.services.queue_service import QueueService
from app.services.rate_limit_service import RateLimitService
from app.services.request_stats_service import RequestStatsService
from app.services.weather_cache_service import WeatherCacheService
from app.services.weather_service import WeatherService
from app.utils.logger import setup_logger
from app.utils.resilience import ResilientRedisPool

logger = setup_logger(__name__)
settings = get_settings()

# Module-level Redis pool instance to be shared across requests
_redis_pool: ResilientRedisPool | None = None


async def get_redis_pool() -> ResilientRedisPool:
    """
    Get or create the Redis connection pool.

    This ensures a single pool instance is used throughout the
    application lifecycle for efficient connection management.

    Returns:
        ResilientRedisPool: Shared Redis connection pool
    """
    global _redis_pool  # pylint: disable=global-statement
    if _redis_pool is None:
        _redis_pool = ResilientRedisPool(settings.redis_url)
        await _redis_pool.health_check()
        logger.info("Redis connection pool initialized")
    return _redis_pool


async def get_redis_client(
    redis_pool: ResilientRedisPool = Depends(get_redis_pool),
) -> AsyncGenerator[redis.Redis, None]:
    """
    Provide Redis client for request lifecycle.

    Args:
        redis_pool: Redis connection pool from dependency

    Yields:
        redis.Redis: Redis client for the request
    """
    client = await redis_pool.get_client()
    try:
        yield client
    finally:
        # Client cleanup if needed (connection returns to pool automatically)
        pass


async def get_weather_cache(
    redis_client: redis.Redis = Depends(get_redis_client),
) -> WeatherCacheService:
    """
    Provide weather cache service instance.

    Args:
        redis_client: Redis client from dependency

    Returns:
        WeatherCacheService: Configured cache service
    """
    return WeatherCacheService(redis_client)


async def get_rate_limiter(
    redis_client: redis.Redis = Depends(get_redis_client),
) -> RateLimitService:
    """
    Provide rate limiting service instance.

    Args:
        redis_client: Redis client from dependency

    Returns:
        RateLimitService: Configured rate limiter
    """
    return RateLimitService(redis_client)


async def get_stats_tracker(
    redis_client: redis.Redis = Depends(get_redis_client),
) -> RequestStatsService:
    """
    Provide request statistics service instance.

    Args:
        redis_client: Redis client from dependency

    Returns:
        RequestStatsService: Configured stats tracker
    """
    return RequestStatsService(redis_client)


async def get_queue_manager(
    redis_client: redis.Redis = Depends(get_redis_client),
) -> QueueService:
    """
    Provide queue management service instance.

    Args:
        redis_client: Redis client from dependency

    Returns:
        QueueService: Configured queue manager
    """
    return QueueService(redis_client)


async def get_weather_service(
    weather_cache: WeatherCacheService = Depends(get_weather_cache),
    rate_limiter: RateLimitService = Depends(get_rate_limiter),
    stats_tracker: RequestStatsService = Depends(get_stats_tracker),
    queue_manager: QueueService = Depends(get_queue_manager),
) -> WeatherService:
    """
    Provide unified weather service with all dependencies.

    This demonstrates proper dependency injection composition where
    FastAPI automatically resolves the dependency graph.

    Args:
        weather_cache: Cache service from dependency
        rate_limiter: Rate limiter from dependency
        stats_tracker: Stats tracker from dependency
        queue_manager: Queue manager from dependency

    Returns:
        WeatherService: Fully configured weather service
    """
    return WeatherService(
        weather_cache=weather_cache,
        rate_limiter=rate_limiter,
        stats_tracker=stats_tracker,
        queue_manager=queue_manager,
    )


async def close_redis_pool():
    """
    Close the Redis connection pool during shutdown.

    This should be called during application shutdown to properly
    clean up Redis connections.
    """
    global _redis_pool  # pylint: disable=global-statement
    if _redis_pool:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Redis connection pool closed")
