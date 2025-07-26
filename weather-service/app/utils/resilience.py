"""
Resilience utilities for handling failures and retries.
"""

import asyncio
import functools
import random
from typing import Callable, TypeVar, ParamSpec, Optional, Type, Tuple
from collections import OrderedDict
from datetime import datetime, UTC

import redis.asyncio as redis

from app.config import get_settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()

P = ParamSpec("P")
T = TypeVar("T")


class InMemoryLRUCache:
    """
    Simple in-memory LRU cache for Redis fallback.

    IMPORTANT: This cache is ONLY used when Redis is completely unavailable.
    It serves as a last-resort fallback to maintain some level of service
    during Redis outages. For normal operations, Redis is the primary cache.
    """

    def __init__(self, max_size: int = 100):
        self.cache: OrderedDict[str, Tuple[any, datetime]] = OrderedDict()
        self.max_size = max_size

    def get(self, key: str) -> Optional[any]:
        """
        Retrieve value from cache if it exists.

        Updates access order for LRU tracking. TTL is not enforced here
        as the cache is meant for short-term fallback during outages.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value if found, None otherwise
        """
        if key in self.cache:
            value, _ = self.cache[key]
            self.cache.move_to_end(key)
            return value
        return None

    def set(self, key: str, value: any, ttl_seconds: int = 3600):
        """
        Store value in cache with LRU eviction policy.

        When cache is at capacity, the least recently used item is evicted.
        The TTL parameter is accepted for interface compatibility but not
        actively enforced, as this cache is designed for short-lived
        emergency fallback scenarios.

        Args:
            key: Cache key
            value: Value to store
            ttl_seconds: TTL in seconds (for interface compatibility)
        """
        if len(self.cache) >= self.max_size and key not in self.cache:
            self.cache.popitem(last=False)

        self.cache[key] = (value, datetime.now(UTC))
        self.cache.move_to_end(key)

    def clear(self):
        """Clear all cache entries."""
        self.cache.clear()


fallback_cache = InMemoryLRUCache(max_size=200)


def redis_retry(
    *,
    max_attempts: Optional[int] = None,
    exceptions: Tuple[Type[Exception], ...] = (
        redis.ConnectionError,
        redis.TimeoutError,
    ),
    backoff_base: float = 2.0,
    use_fallback: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for Redis operations with automatic retry and optional fallback.

    Implements an exponential backoff retry strategy for handling transient
    Redis failures. When all retries are exhausted and a fallback method
    is configured, it seamlessly switches to an in-memory cache to maintain
    service availability during Redis outages.

    Retry behavior:
    - Exponential backoff: wait_time = backoff_base^attempt + random_jitter
    - Only retries on specified exceptions (connection/timeout by default)
    - Logs warnings during retries and errors when all attempts fail

    Fallback behavior:
    - Activated only after all retry attempts are exhausted
    - Requires the decorated method to have @with_fallback decorator
    - Fallback method receives the same arguments (minus self for instance methods)

    Args:
        max_attempts: Maximum retry attempts (defaults to settings.retry_max_attempts)
        exceptions: Tuple of exceptions that trigger retries
        backoff_base: Base for exponential backoff calculation
        use_fallback: Whether to attempt fallback method on complete failure

    Returns:
        Decorated function with retry and fallback capabilities
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            attempts = max_attempts or settings.retry_max_attempts
            last_exception = None

            for attempt in range(attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < attempts - 1:
                        wait_time = (backoff_base**attempt) + random.uniform(
                            settings.retry_wait_random_min,
                            settings.retry_wait_random_max,
                        )
                        logger.warning(
                            "Redis operation failed, retrying",
                            extra={
                                "event": "redis_retry_attempt",
                                "attempt": attempt + 1,
                                "max_attempts": attempts,
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "operation": func.__name__,
                                "wait_time_seconds": round(wait_time, 2),
                            },
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            "Redis operation failed after all attempts",
                            extra={
                                "event": "redis_retry_exhausted",
                                "max_attempts": attempts,
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "operation": func.__name__,
                            },
                        )

            if use_fallback and hasattr(func, "_fallback_method_name"):
                if args and hasattr(args[0], func._fallback_method_name):
                    instance = args[0]
                    fallback_method = getattr(instance, func._fallback_method_name)
                    logger.info(
                        "Using fallback method after Redis failure",
                        extra={
                            "event": "redis_fallback_used",
                            "fallback_method": func._fallback_method_name,
                            "original_method": func.__name__,
                        },
                    )
                    return await fallback_method(*args[1:], **kwargs)

            raise last_exception

        if hasattr(func, "_fallback_method_name"):
            wrapper._fallback_method_name = func._fallback_method_name

        return wrapper

    return decorator


def with_fallback(
    fallback_method_name: str,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to specify a fallback method for Redis operation failures.

    This decorator works in conjunction with @redis_retry to provide a
    seamless fallback mechanism. It attaches metadata to the decorated
    method indicating which fallback method should be called when all
    Redis retry attempts are exhausted.

    The fallback method must:
    - Be defined on the same class as the decorated method
    - Accept the same parameters (excluding 'self')
    - Return the same type as the decorated method

    Usage example:
        class CacheService:
            async def _get_fallback(self, key: str) -> Optional[str]:
                return self.memory_cache.get(key)

            @redis_retry(use_fallback=True)
            @with_fallback("_get_fallback")
            async def get(self, key: str) -> Optional[str]:
                return await self.redis.get(key)

    Args:
        fallback_method_name: Name of the instance method to use as fallback

    Returns:
        Decorator function that attaches fallback metadata
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        setattr(func, "_fallback_method_name", fallback_method_name)
        return func

    return decorator


class ResilientRedisPool:
    """
    Redis connection pool with enhanced reliability features.

    Provides a managed Redis connection pool with automatic reconnection,
    connection keepalive, and health monitoring capabilities. Designed
    for high-availability scenarios where Redis connectivity is critical.

    Features:
    - Lazy initialization of connection pool
    - TCP keepalive for long-lived connections
    - Built-in health check functionality
    - Graceful connection cleanup

    The pool maintains a single shared client instance to optimize
    resource usage while ensuring connection reliability through
    keepalive settings.
    """

    def __init__(self, redis_url: str, max_connections: int = 50):
        """
        Initialize resilient Redis pool configuration.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
            max_connections: Maximum number of connections in the pool
        """
        self.redis_url = redis_url
        self.max_connections = max_connections
        self._pool = None
        self._client = None
        self._healthy = True

    async def get_client(self) -> redis.Redis:
        """
        Get or create Redis client with connection pool.

        Lazily initializes the connection pool on first access. Subsequent
        calls return the same client instance. The pool is configured with
        TCP keepalive to maintain connection health.

        Returns:
            Redis client instance with connection pooling
        """
        if self._client is None:
            self._pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=settings.redis_decode_responses,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,
                    2: 30,
                    3: 5,
                },
            )
            self._client = redis.Redis(connection_pool=self._pool)

        return self._client

    async def close(self):
        """
        Close the connection pool and clean up resources.

        Disconnects all connections in the pool and resets internal state.
        This method should be called during application shutdown to ensure
        graceful cleanup of Redis connections.
        """
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
            self._client = None

    async def health_check(self) -> bool:
        """
        Perform health check on Redis connection.

        Attempts to ping the Redis server to verify connectivity.
        Updates internal health status based on the result.

        Returns:
            True if Redis is reachable and responding, False otherwise

        Note:
            Failed health checks are logged but don't prevent future
            connection attempts, allowing for automatic recovery.
        """
        try:
            client = await self.get_client()
            await client.ping()
            self._healthy = True
            return True
        except Exception as e:
            logger.error(
                "Redis health check failed",
                extra={
                    "event": "redis_health_check_failed",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            self._healthy = False
            return False
