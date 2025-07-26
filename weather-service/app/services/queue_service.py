"""
Priority queue service for background job processing.
"""

from typing import Optional

import redis.asyncio as redis

from app.utils.logger import setup_logger
from app.utils.resilience import redis_retry

logger = setup_logger(__name__)


class QueueService:
    """
    Service responsible for priority queue operations.

    Uses Redis sorted sets for priority-based job queuing.
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize queue service.
        """
        self.redis_client = redis_client

    @redis_retry(use_fallback=False)
    async def add_to_queue(self, city: str, priority: int = 0):
        """
        Add city to processing queue with priority.

        Lower scores have higher priority in Redis sorted sets.
        """
        queue_key = "weather:queue:cities"
        score = -priority
        await self.redis_client.zadd(queue_key, {city.lower(): score})
        logger.info(
            "Added city to queue",
            extra={
                "event": "queue_add",
                "city": city,
                "priority": priority,
                "queue_key": "weather:queue:cities",
            },
        )

    @redis_retry(use_fallback=False)
    async def get_from_queue(self) -> Optional[str]:
        """
        Get next city from processing queue (highest priority first).
        """
        queue_key = "weather:queue:cities"
        result = await self.redis_client.zpopmin(queue_key)

        if result:
            city = result[0][0]
            return city.decode() if isinstance(city, bytes) else city
        return None

    @redis_retry(use_fallback=False)
    async def get_queue_size(self) -> int:
        """
        Get current queue size.
        """
        queue_key = "weather:queue:cities"
        return await self.redis_client.zcard(queue_key)

    @redis_retry(use_fallback=False)
    async def clear_queue(self):
        """
        Clear all items from the queue.
        """
        queue_key = "weather:queue:cities"
        await self.redis_client.delete(queue_key)
        logger.info(
            "Queue cleared",
            extra={"event": "queue_clear", "queue_key": "weather:queue:cities"},
        )
