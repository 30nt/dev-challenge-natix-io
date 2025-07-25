"""
Priority queue service for background job processing.
"""

from typing import Optional

import redis.asyncio as redis

from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class QueueService:
    """
    Service responsible for priority queue operations.

    Uses Redis sorted sets for priority-based job queuing.
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize queue service.

        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client

    async def add_to_queue(self, city: str, priority: int = 0):
        """
        Add city to processing queue with priority.

        Lower scores have higher priority in Redis sorted sets.
        """
        try:
            queue_key = "weather:queue:cities"
            score = -priority  # Negative for higher priority first
            await self.redis_client.zadd(queue_key, {city.lower(): score})
            logger.info("Added %s to queue with priority %s", city, priority)

        except redis.ConnectionError:
            logger.error("Redis connection failed while adding %s to queue", city)
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while adding %s to queue", city)
        except Exception as e:
            logger.error("Unexpected error adding %s to queue: %s", city, e)

    async def get_from_queue(self) -> Optional[str]:
        """
        Get next city from processing queue (highest priority first).
        """
        try:
            queue_key = "weather:queue:cities"
            result = await self.redis_client.zpopmin(queue_key)

            if result:
                city = result[0][0]
                return city.decode() if isinstance(city, bytes) else city
            return None

        except redis.ConnectionError:
            logger.error("Redis connection failed while getting from queue")
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while getting from queue")
            return None
        except Exception as e:
            logger.error("Unexpected error getting from queue: %s", e)
            return None

    async def get_queue_size(self) -> int:
        """
        Get current queue size.
        """
        try:
            queue_key = "weather:queue:cities"
            return await self.redis_client.zcard(queue_key)

        except redis.ConnectionError:
            logger.error("Redis connection failed while getting queue size")
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while getting queue size")
            return 0
        except Exception as e:
            logger.error("Unexpected error getting queue size: %s", e)
            return 0

    async def clear_queue(self):
        """
        Clear all items from the queue.
        """
        try:
            queue_key = "weather:queue:cities"
            await self.redis_client.delete(queue_key)
            logger.info("Queue cleared")

        except redis.ConnectionError:
            logger.error("Redis connection failed while clearing queue")
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while clearing queue")
        except Exception as e:
            logger.error("Unexpected error clearing queue: %s", e)
