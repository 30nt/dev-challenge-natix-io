"""
This module handles the cache warming process.
"""

import asyncio

from app.config import get_settings
from app.definitions.data_sources import DEFAULT_CITIES
from app.middleware.dependency_container import container
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


async def warm_cache(app):
    """
    Warms the cache by fetching weather data for top cities.
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

        top_cities = await stats_tracker.get_top_cities(settings.top_cities_count)

        if not top_cities:
            top_cities = [
                (city, 0) for city in DEFAULT_CITIES[: settings.top_cities_count]
            ]

        tokens_to_use = min(
            len(top_cities),
            settings.cache_warm_max_tokens,
            remaining_tokens - settings.cache_warm_min_tokens_remaining,
        )

        if tokens_to_use <= 0:
            logger.info("No tokens available for cache warming")
            return

        logger.info(
            "Warming cache for %s cities (of %s top cities)",
            tokens_to_use,
            len(top_cities),
        )

        warmed_count = 0
        for city, _ in top_cities:
            if warmed_count >= tokens_to_use:
                break

            try:
                if await rate_limiter.consume_rate_limit_token():
                    await weather_service.get_weather(city)
                    logger.debug("Warmed cache for %s", city)
                    warmed_count += 1
                    await asyncio.sleep(0.5)
                else:
                    logger.warning("Rate limit reached during cache warming")
                    break
            except ValueError as e:
                logger.error("Failed to warm cache for %s: %s", city, e)

        logger.info("Cache warming completed: warmed %s cities", warmed_count)

    except ValueError as e:
        logger.error("Cache warming failed: %s", e)


async def cache_warmer_task(app):
    """
    Continuously runs the cache warming task.
    """
    while True:
        try:
            await warm_cache(app)
            await asyncio.sleep(settings.cache_warm_interval)
        except asyncio.CancelledError:
            logger.info("Cache warmer task cancelled")
            break
        except ValueError as e:
            logger.error("Cache warmer error: %s", e)
            await asyncio.sleep(60)


async def start_cache_warmer(app):
    """
    Starts the cache warmer task.
    """
    task = asyncio.create_task(cache_warmer_task(app))
    return task
