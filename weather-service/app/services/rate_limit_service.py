"""
Rate limiting service using Redis with atomic operations.
"""

import redis.asyncio as redis
from limits.storage import RedisStorage
from limits.strategies import MovingWindowRateLimiter
from limits.util import parse_many

from app.config import get_settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class RateLimitService:
    """
    Service responsible for distributed rate limiting using Redis with atomic operations.

    Uses the 'limits' library which provides thread-safe, atomic operations
    and supports moving window rate limiting for better request distribution.
    """

    def __init__(self, redis_client: redis.Redis = None):
        """
        Initialize rate limit service with Redis backend.
        """

        self.storage = RedisStorage(settings.redis_url)

        self.limiter = MovingWindowRateLimiter(self.storage)

        self.rate_limit_str = (
            f"{settings.rate_limit_requests} per {settings.rate_limit_window} seconds"
        )
        self.rate_limits = parse_many(self.rate_limit_str)

        logger.info("Initialized rate limiter with limit: %s", self.rate_limit_str)

    async def get_rate_limit_remaining(self, identifier: str = "global") -> int:
        """
        Get remaining rate limit tokens for the given identifier.
        """
        try:

            rate_limit = self.rate_limits[0]

            _, current_usage = self.limiter.get_window_stats(rate_limit, identifier)

            remaining = max(0, rate_limit.amount - current_usage)

            return remaining

        except Exception as e:
            logger.error("Error getting rate limit remaining: %s", e)
            return 0

    async def consume_rate_limit_token(self, identifier: str = "global") -> bool:
        """
        Consume a rate limit token for the given identifier.

        This method is atomic and thread-safe, eliminating race conditions.
        """
        try:

            for rate_limit in self.rate_limits:
                if not self.limiter.hit(rate_limit, identifier):
                    logger.warning(
                        "Rate limit exceeded for %s: %s", identifier, rate_limit
                    )
                    return False

            logger.debug("Rate limit token consumed for %s", identifier)
            return True

        except Exception as e:
            logger.error("Error consuming rate limit token: %s", e)

            return False
