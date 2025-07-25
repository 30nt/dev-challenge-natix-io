"""
Request statistics tracking service.
"""

from typing import List

import redis.asyncio as redis

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class RequestStatsService:
    """
    Service responsible for tracking request statistics.

    Uses Redis sorted sets for efficient top cities queries.
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize request stats service.
        """
        self.redis_client = redis_client

    def _get_stats_key(self, city: str) -> str:
        """
        Generate cache key for request statistics.
        """
        return f"weather:stats:{city.lower()}:request_count"

    async def increment_stats(self, city: str):
        """
        Increment request statistics for a city.

        Uses both individual counters and sorted set for efficiency.
        """
        try:

            stats_key = self._get_stats_key(city)
            await self.redis_client.incr(stats_key)
            await self.redis_client.expire(stats_key, 86400 * 7)

            await self.redis_client.zincrby("top_cities", 1, city.lower())
            await self.redis_client.expire("top_cities", 86400 * 7)

        except redis.ConnectionError:
            logger.error(
                "Redis connection failed while incrementing stats for %s", city
            )
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while incrementing stats for %s", city)
        except Exception as e:
            logger.error("Unexpected error incrementing stats for %s: %s", city, e)

    async def get_top_cities(self, count: int = 50) -> List[tuple[str, int]]:
        """
        Get top cities by request count using Redis sorted sets.

        Much more efficient than scanning all keys.
        """
        try:

            result = await self.redis_client.zrevrange(
                "top_cities", 0, count - 1, withscores=True
            )

            return [
                (city.decode() if isinstance(city, bytes) else city, int(score))
                for city, score in result
            ]

        except redis.ConnectionError:
            logger.error("Redis connection failed while getting top cities")
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while getting top cities")
            return []
        except Exception as e:
            logger.error("Unexpected error getting top cities: %s", e)
            return []

    async def get_city_stats(self, city: str) -> int:
        """
        Get request count for a specific city.
        """
        try:
            score = await self.redis_client.zscore("top_cities", city.lower())
            return int(score) if score else 0

        except redis.ConnectionError:
            logger.error("Redis connection failed while getting stats for %s", city)
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while getting stats for %s", city)
            return 0
        except Exception as e:
            logger.error("Unexpected error getting stats for %s: %s", city, e)
            return 0
