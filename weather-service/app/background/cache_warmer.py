import asyncio

from app.config import get_settings
from app.definitions.data_sources import DEFAULT_CITIES
from app.services.weather_service import WeatherService
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


async def warm_cache(app):
    cache_service = app.state.cache_service
    weather_service = WeatherService(cache_service)

    try:
        remaining_tokens = await cache_service.get_rate_limit_remaining()

        if remaining_tokens < settings.cache_warm_min_tokens_remaining:
            logger.info(
                f"Skipping cache warming: only {remaining_tokens} tokens remaining"
            )
            return

        top_cities = await cache_service.get_top_cities(settings.top_cities_count)

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
            f"Warming cache for {tokens_to_use} cities (of {len(top_cities)} top cities)"
        )

        warmed_count = 0
        for city, _ in top_cities:
            if warmed_count >= tokens_to_use:
                break

            try:
                if await cache_service.consume_rate_limit_token():
                    await weather_service.get_weather(city)
                    logger.debug(f"Warmed cache for {city}")
                    warmed_count += 1
                    await asyncio.sleep(0.5)  # Be gentle on the API
                else:
                    logger.warning("Rate limit reached during cache warming")
                    break
            except Exception as e:
                logger.error(f"Failed to warm cache for {city}: {e}")

        logger.info(f"Cache warming completed: warmed {warmed_count} cities")

    except Exception as e:
        logger.error(f"Cache warming failed: {e}")


async def cache_warmer_task(app):
    while True:
        try:
            await warm_cache(app)
            await asyncio.sleep(settings.cache_warm_interval)
        except asyncio.CancelledError:
            logger.info("Cache warmer task cancelled")
            break
        except Exception as e:
            logger.error(f"Cache warmer error: {e}")
            await asyncio.sleep(60)


async def start_cache_warmer(app):
    task = asyncio.create_task(cache_warmer_task(app))
    return task
