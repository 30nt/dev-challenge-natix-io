"""
This module handles the cache warming process.
"""

import asyncio
from typing import List, Tuple
from datetime import date

from app.config import get_settings
from app.definitions.data_sources import DEFAULT_CITIES, ApiVersion
from app.middleware.dependency_container import container
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


async def warm_single_city(
    city: str, weather_service, semaphore: asyncio.Semaphore
) -> None:
    """
    Warm cache for a single city with concurrency control.
    """
    async with semaphore:
        try:
            await weather_service.get_weather(city, ApiVersion.V2)
            logger.debug("Warmed cache for %s", city)
        except Exception as e:
            logger.error("Failed to warm cache for %s: %s", city, e)


async def get_cities_to_warm(stats_tracker, max_cities: int) -> List[Tuple[str, int]]:
    """
    Get prioritized list of cities to warm.
    """
    top_cities = await stats_tracker.get_top_cities(max_cities * 2)

    if not top_cities:
        return [(city, 0) for city in DEFAULT_CITIES[:max_cities]]

    today_date = date.today().isoformat()
    weather_cache = container.weather_cache

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


async def warm_cache(app):
    """
    Warms the cache by fetching weather data for top cities concurrently.
    """
    weather_service = container.weather_service
    rate_limiter = container.rate_limiter
    stats_tracker = container.stats_tracker

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

        cities_to_warm = await get_cities_to_warm(stats_tracker, tokens_to_use)

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
    Starts the cache warmer task.
    """
    if not settings.enable_cache_warming:
        logger.info("Cache warming is disabled")
        return None

    task = asyncio.create_task(cache_warmer_task(app))
    return task
