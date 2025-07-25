"""
Rate limiting service using Redis.
"""

import redis.asyncio as redis

from app.config import get_settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class RateLimitService:
    """
    Service responsible for distributed rate limiting using Redis.

    Uses a simple counter/stack approach: initialize with max tokens (100),
    decrement on each external API call, reset when window expires.
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize rate limit service.

        Args:
            redis_client: Redis client instance
        """
        self.redis_client = redis_client

    async def get_rate_limit_remaining(self) -> int:
        """
        Get remaining rate limit tokens.
        """
        try:
            key = "rate_limit:tokens"
            tokens = await self.redis_client.get(key)
            return int(tokens) if tokens else settings.rate_limit_requests

        except redis.ConnectionError:
            logger.error("Redis connection failed while getting rate limit")
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while getting rate limit")
            return 0
        except ValueError as e:
            logger.error("Invalid token value in Redis: %s", e)
            return 0
        except Exception as e:
            logger.error("Unexpected error getting rate limit: %s", e)
            return 0

    async def consume_rate_limit_token(self) -> bool:
        """
        Consume a rate limit token.

        Uses simple Redis operations - initializes bucket if needed.
        Small race condition possible but acceptable for 100/hour rate.
        """
        try:
            key = "rate_limit:tokens"

            # Check if bucket exists
            current = await self.redis_client.get(key)
            if current is None:
                # Initialize bucket with max tokens
                await self.redis_client.setex(
                    key, settings.rate_limit_window, settings.rate_limit_requests
                )
                current = str(settings.rate_limit_requests)

            # Try to consume token
            remaining = int(current)
            if remaining > 0:
                await self.redis_client.decr(key)
                return True

            return False

        except redis.ConnectionError:
            logger.error("Redis connection failed while consuming rate limit token")
            raise
        except redis.TimeoutError:
            logger.warning("Redis timeout while consuming rate limit token")
            return False
        except Exception as e:
            logger.error("Unexpected error consuming rate limit token: %s", e)
            return False
