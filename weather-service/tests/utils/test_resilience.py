"""
Tests for resilience utilities.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis.asyncio as redis

from app.utils.resilience import (
    InMemoryLRUCache,
    redis_retry,
    with_fallback,
    ResilientRedisPool,
)


class TestInMemoryLRUCache:
    """Test suite for the in-memory LRU cache implementation.

    Verifies basic cache operations, LRU eviction policy, and edge cases
    for the fallback cache used during Redis outages.
    """

    def test_basic_operations(self):
        """Test basic cache operations including get, set, and clear.

        Validates that:
        - Items can be stored and retrieved correctly
        - Non-existent keys return None
        - Clear operation removes all cached items
        """
        cache = InMemoryLRUCache(max_size=3)

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        assert cache.get("nonexistent") is None

        cache.clear()
        assert cache.get("key1") is None

    def test_lru_eviction(self):
        """Test LRU eviction policy when cache reaches capacity.

        Verifies that when the cache is full, adding a new item evicts
        the least recently used item. Access operations update the
        usage order, protecting recently accessed items from eviction.
        """
        cache = InMemoryLRUCache(max_size=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.get("key1")

        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"


class TestRedisRetry:
    """Test suite for Redis retry decorator with exponential backoff.

    Validates retry logic, fallback mechanisms, and error handling
    for Redis operations under various failure scenarios.
    """

    @pytest.mark.asyncio
    async def test_successful_operation(self):
        """Test that successful operations complete without retries.

        Verifies that when a Redis operation succeeds on the first
        attempt, no retry logic is triggered and the result is
        returned immediately.
        """

        @redis_retry(max_attempts=3)
        async def successful_operation():
            return "success"

        result = await successful_operation()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Test retry mechanism on transient Redis connection errors.

        Simulates a scenario where Redis connections fail initially
        but succeed after retries. Validates that the decorator
        retries the configured number of times before succeeding.
        """
        call_count = 0

        @redis_retry(max_attempts=3, backoff_base=0.01)
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise redis.ConnectionError("Connection failed")
            return "success"

        result = await failing_then_success()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """Test behavior when all retry attempts are exhausted.

        Verifies that when an operation continues to fail after
        the maximum number of retry attempts, the original
        exception is re-raised to the caller.
        """

        @redis_retry(max_attempts=2, backoff_base=0.1)
        async def always_fails():
            raise redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await always_fails()

    @pytest.mark.asyncio
    async def test_with_fallback(self):
        """Test fallback mechanism when Redis operations fail.

        Validates that when Redis operations fail after all retry
        attempts, the specified fallback method is invoked to
        provide degraded service rather than complete failure.
        """

        class TestService:
            async def _fallback_method(self, value):
                return f"fallback: {value}"

            @redis_retry(max_attempts=1, use_fallback=True)
            @with_fallback("_fallback_method")
            async def operation_with_fallback(self, value):
                raise redis.ConnectionError("Connection failed")

        service = TestService()
        result = await service.operation_with_fallback("test")
        assert result == "fallback: test"


class TestResilientRedisPool:
    """Test suite for resilient Redis connection pool.

    Validates connection pooling, health checks, and graceful
    degradation features of the enhanced Redis pool implementation.
    """

    @pytest.mark.asyncio
    async def test_pool_initialization(self):
        """Test lazy initialization of Redis connection pool.

        Verifies that the pool is created on first access and
        properly configures the Redis client with enhanced
        connection parameters.
        """
        pool = ResilientRedisPool("redis://localhost:6379")

        with patch("redis.asyncio.ConnectionPool.from_url") as mock_pool:
            with patch("redis.asyncio.Redis") as mock_redis:
                client = await pool.get_client()

                assert mock_pool.called
                assert mock_redis.called
                assert client is not None

    @pytest.mark.asyncio
    async def test_pool_reuse(self):
        """Test connection pool reuse for efficiency.

        Validates that multiple get_client calls return the same
        client instance, avoiding unnecessary connection creation
        and improving performance.
        """
        pool = ResilientRedisPool("redis://localhost:6379")

        with patch("redis.asyncio.ConnectionPool.from_url") as mock_pool:
            with patch("redis.asyncio.Redis") as mock_redis:
                client1 = await pool.get_client()
                client2 = await pool.get_client()

                assert mock_pool.call_count == 1
                assert mock_redis.call_count == 1
                assert client1 is client2

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check when Redis is responsive.

        Verifies that successful ping operations mark the pool
        as healthy, enabling normal operations to proceed.
        """
        pool = ResilientRedisPool("redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)

        with patch.object(pool, "get_client", return_value=mock_client):
            result = await pool.health_check()

            assert result is True
            assert pool._healthy is True
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check when Redis is unavailable.

        Validates that connection failures during health checks
        properly mark the pool as unhealthy, triggering fallback
        mechanisms in dependent services.
        """
        pool = ResilientRedisPool("redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=redis.ConnectionError("Failed"))

        with patch.object(pool, "get_client", return_value=mock_client):
            result = await pool.health_check()

            assert result is False
            assert pool._healthy is False

    @pytest.mark.asyncio
    async def test_pool_close(self):
        """Test graceful shutdown of connection pool.

        Ensures that closing the pool properly disconnects all
        connections and cleans up resources to prevent leaks.
        """
        pool = ResilientRedisPool("redis://localhost:6379")

        mock_pool = AsyncMock()
        pool._pool = mock_pool
        pool._client = MagicMock()

        await pool.close()

        mock_pool.disconnect.assert_called_once()
        assert pool._pool is None
        assert pool._client is None
