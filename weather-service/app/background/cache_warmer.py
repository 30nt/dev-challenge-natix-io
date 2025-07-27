"""
This module handles the cache warming process.
"""

import asyncio
from datetime import date
from typing import List, Tuple

from app.config import get_settings
from app.definitions.data_sources import DEFAULT_CITIES, ApiVersion
from app.services.rate_limit_service import RateLimitService
from app.services.request_stats_service import RequestStatsService
from app.services.weather_cache_service import WeatherCacheService
from app.services.weather_service import WeatherService
from app.utils.dependencies import get_redis_pool
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


async def warm_single_city(
    city: str, weather_service, semaphore: asyncio.Semaphore
) -> None:
    """
    Warm cache for a single city with concurrency control.

    This function fetches weather data for a city to ensure it's cached.
    Uses a semaphore to limit concurrent requests and prevent overwhelming
    the external API.

    Args:
        city: City name to warm cache for
        weather_service: Weather service instance to use
        semaphore: Asyncio semaphore for concurrency control
    """
    async with semaphore:
        try:
            await weather_service.get_weather(city, ApiVersion.V2)
            logger.debug("Warmed cache for %s", city)
        except Exception as e:
            logger.error("Failed to warm cache for %s: %s", city, e)


async def get_cities_to_warm(
    stats_tracker, weather_cache, max_cities: int
) -> List[Tuple[str, int]]:
    """
    Get prioritized list of cities to warm based on usage statistics.

    This function retrieves the most requested cities and prioritizes
    those without cached data. If no statistics are available, it falls
    back to a default list of cities.

    The prioritization strategy:
    1. Cities without cache come first (they need warming most)
    2. Cities with cache come second (to refresh if needed)
    3. Limited to max_cities to control resource usage

    Args:
        stats_tracker: Request statistics service
        weather_cache: Weather cache service to check existing cache
        max_cities: Maximum number of cities to return

    Returns:
        List of tuples containing (city_name, request_count)
    """
    top_cities = await stats_tracker.get_top_cities(max_cities * 2)

    if not top_cities:
        return [(city, 0) for city in DEFAULT_CITIES[:max_cities]]

    today_date = date.today().isoformat()

    cities_needing_cache = []
    cities_with_cache = []

    for city, count in top_cities:
        cached_data = await weather_cache.get_weather(city, today_date)
        if cached_data:
            cities_with_cache.append((city, count))
        else:
            cities_needing_cache.append((city, count))

    prioritized = cities_needing_cache + cities_with_cache
    return prioritized[:max_cities]


async def warm_cache(app):  # pylint: disable=unused-argument,too-many-locals
    """
    Warms the cache by fetching weather data for top cities concurrently.

    This function implements intelligent cache warming with the following features:
    - Respects rate limits by checking available tokens before warming
    - Uses only a portion of available tokens to leave room for user requests
    - Prioritizes cities based on usage statistics and cache status
    - Implements concurrent warming with controlled parallelism
    - Handles failures gracefully without affecting the entire process

    The warming process:
    1. Check rate limit status and calculate safe token usage
    2. Get prioritized list of cities needing cache updates
    3. Warm caches concurrently with semaphore-based throttling
    4. Log results for monitoring and debugging

    Args:
        app: FastAPI application instance
    """
    redis_pool = await get_redis_pool()
    redis_client = await redis_pool.get_client()

    weather_cache = WeatherCacheService(redis_client)
    rate_limiter = RateLimitService(redis_client)
    stats_tracker = RequestStatsService(redis_client)
    weather_service = WeatherService(
        weather_cache=weather_cache,
        rate_limiter=rate_limiter,
        stats_tracker=stats_tracker,
        queue_manager=None,  # Not needed for cache warming in Demo
    )

    try:
        remaining_tokens = await rate_limiter.get_rate_limit_remaining()

        if remaining_tokens < settings.cache_warm_min_tokens_remaining:
            logger.info(
                "Skipping cache warming: only %s tokens remaining", remaining_tokens
            )
            return

        tokens_to_use = min(
            settings.cache_warm_max_tokens,
            int(remaining_tokens * 0.2),
            remaining_tokens - settings.cache_warm_min_tokens_remaining,
        )

        if tokens_to_use <= 0:
            logger.info("No tokens available for cache warming")
            return

        cities_to_warm = await get_cities_to_warm(
            stats_tracker, weather_cache, tokens_to_use
        )

        logger.info(
            "Warming cache for %s cities concurrently",
            len(cities_to_warm),
        )

        max_concurrent = min(5, len(cities_to_warm))
        semaphore = asyncio.Semaphore(max_concurrent)

        tasks = []
        for city, _ in cities_to_warm:
            if await rate_limiter.consume_rate_limit_token():
                task = warm_single_city(city, weather_service, semaphore)
                tasks.append(task)
            else:
                logger.warning("Rate limit reached during cache warming")
                break

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            warmed_count = sum(1 for r in results if r is True)
            logger.info("Cache warming completed: warmed %s cities", warmed_count)
        else:
            logger.info("No cities warmed due to rate limiting")

    except Exception as e:
        logger.error("Cache warming failed: %s", e)


async def cache_warmer_task(app):
    """
    Continuously runs the cache warming task.

    This background task runs indefinitely, periodically warming the cache
    based on the configured interval. It includes error handling to ensure
    the task continues running even if individual warming attempts fail.

    The task lifecycle:
    1. Initial delay to let the application fully start
    2. Continuous loop executing cache warming
    3. Graceful cancellation handling for shutdown
    4. Error recovery with backoff on failures

    Args:
        app: FastAPI application instance
    """
    await asyncio.sleep(30)

    while True:
        try:
            await warm_cache(app)
            await asyncio.sleep(settings.cache_warm_interval)
        except asyncio.CancelledError:
            logger.info("Cache warmer task cancelled")
            break
        except Exception as e:
            logger.error("Cache warmer error: %s", e)
            await asyncio.sleep(60)


async def start_cache_warmer(app):
    """
    Starts the cache warmer background task.

    This function checks if cache warming is enabled in settings
    and creates an asyncio task to run the warmer in the background.
    The task runs independently and doesn't block the main application.

    Args:
        app: FastAPI application instance

    Returns:
        asyncio.Task or None: The created task if warming is enabled,
                              None if disabled
    """
    if not settings.enable_cache_warming:
        logger.info("Cache warming is disabled")
        return None

    task = asyncio.create_task(cache_warmer_task(app))
    return task
