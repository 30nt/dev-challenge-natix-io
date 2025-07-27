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

        window_seconds = settings.rate_limit_window
        logger.info(
            "Initialized rate limiter",
            extra={
                "event": "rate_limiter_init",
                "limit": self.rate_limit_str,
                "window_seconds": window_seconds,
            },
        )

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
            logger.error(
                "Error getting rate limit remaining",
                extra={
                    "event": "rate_limit_error",
                    "operation": "get_remaining",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
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
                        "Rate limit exceeded",
                        extra={
                            "event": "rate_limit_exceeded",
                            "identifier": identifier,
                            "limit": str(rate_limit),
                        },
                    )
                    return False

            logger.debug(
                "Rate limit token consumed",
                extra={"event": "rate_limit_consumed", "identifier": identifier},
            )
            return True

        except Exception as e:
            logger.error(
                "Error consuming rate limit token",
                extra={
                    "event": "rate_limit_error",
                    "operation": "consume_token",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

            return False
