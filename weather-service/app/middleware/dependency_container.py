"""
This module provides a dependency container for the application.
"""

import redis.asyncio as redis

from app.config import get_settings
from app.services.queue_service import QueueService
from app.services.rate_limit_service import RateLimitService
from app.services.request_stats_service import RequestStatsService
from app.services.weather_cache_service import WeatherCacheService
from app.services.weather_service import WeatherService
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class DependencyContainer:
    """
    Dependency injection container for application services.

    Manages service instances and their dependencies with direct service injection.
    """

    def __init__(self):
        """
        Initialize container with empty services.
        """
        self.redis_client = None
        self.weather_cache = None
        self.rate_limiter = None
        self.stats_tracker = None
        self.queue_manager = None
        self.weather_service = None

    async def initialize(self):
        """
        Initialize Redis connection and all services.
        """
        try:

            self.redis_client = redis.from_url(
                settings.redis_url, decode_responses=settings.redis_decode_responses
            )
            await self.redis_client.ping()

            self.weather_cache = WeatherCacheService(self.redis_client)
            self.rate_limiter = RateLimitService(self.redis_client)
            self.stats_tracker = RequestStatsService(self.redis_client)
            self.queue_manager = QueueService(self.redis_client)

            self.weather_service = WeatherService(
                weather_cache=self.weather_cache,
                rate_limiter=self.rate_limiter,
                stats_tracker=self.stats_tracker,
                queue_manager=self.queue_manager,
            )

            logger.info("All services initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize services: %s", e)
            raise

    async def close(self):
        """
        Close Redis connection.
        """
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")


container = DependencyContainer()
