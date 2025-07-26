"""
Tests for the queue service module.
"""

from unittest.mock import AsyncMock

import pytest
import redis.asyncio as redis

from app.services.queue_service import QueueService


@pytest.fixture
def mock_redis():
    """Create a mock Redis client for testing.

    Returns:
        AsyncMock: Mocked Redis client with async methods
    """
    return AsyncMock()


@pytest.fixture
def queue_service(mock_redis):
    """Create a QueueService instance with mocked dependencies.

    Args:
        mock_redis: Mocked Redis client fixture

    Returns:
        QueueService: Configured queue service for testing
    """
    return QueueService(mock_redis)


class TestQueueService:
    """Test suite for priority queue service operations.

    Validates queue management functionality including adding items,
    retrieving by priority, and handling Redis failures with retries.
    """

    async def test_add_to_queue_success(self, queue_service, mock_redis):
        """Test successful addition of city to priority queue.

        Verifies that cities are added with correct priority scores
        (negative for Redis sorted set ordering) and city names are
        normalized to lowercase.
        """
        mock_redis.zadd.return_value = 1

        await queue_service.add_to_queue("London", priority=5)

        mock_redis.zadd.assert_called_once_with("weather:queue:cities", {"london": -5})

    async def test_add_to_queue_default_priority(self, queue_service, mock_redis):
        """Test queue addition with default priority value.

        Validates that when no priority is specified, items are
        added with priority 0 (neutral priority).
        """
        mock_redis.zadd.return_value = 1

        await queue_service.add_to_queue("London")

        mock_redis.zadd.assert_called_once_with("weather:queue:cities", {"london": 0})

    async def test_add_to_queue_connection_error(self, queue_service, mock_redis):
        """Test connection error handling during queue operations.

        Verifies that Redis connection errors are propagated after
        retry attempts are exhausted, allowing upstream error handling.
        """
        mock_redis.zadd.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await queue_service.add_to_queue("London", priority=5)

    async def test_add_to_queue_timeout_error(self, queue_service, mock_redis):
        """Test retry mechanism on Redis timeout errors.

        Validates that timeout errors trigger the retry decorator,
        attempting the operation multiple times before failing.
        The default configuration attempts 3 times.
        """
        mock_redis.zadd.side_effect = redis.TimeoutError("Timeout")

        with pytest.raises(redis.TimeoutError):
            await queue_service.add_to_queue("London", priority=5)

        assert mock_redis.zadd.call_count == 3

    async def test_add_to_queue_general_error(self, queue_service, mock_redis):
        """Test handling of unexpected errors without retry.

        Verifies that non-Redis exceptions are not retried,
        as they likely indicate programming errors rather than
        transient infrastructure issues.
        """
        mock_redis.zadd.side_effect = Exception("General error")

        with pytest.raises(Exception) as exc_info:
            await queue_service.add_to_queue("London", priority=5)

        assert str(exc_info.value) == "General error"
        mock_redis.zadd.assert_called_once()

    async def test_get_from_queue_success(self, queue_service, mock_redis):
        """Test retrieving highest priority item from queue.

        Validates that zpopmin correctly returns the item with
        the lowest score (highest priority) and handles byte
        string decoding from Redis.
        """

        mock_redis.zpopmin.return_value = [(b"london", -10.0)]

        city = await queue_service.get_from_queue()

        assert city == "london"
        mock_redis.zpopmin.assert_called_once_with("weather:queue:cities")

    async def test_get_from_queue_string_result(self, queue_service, mock_redis):
        """Test queue retrieval with pre-decoded string values.

        Ensures the service handles both byte strings and regular
        strings from Redis, maintaining compatibility with different
        Redis client configurations.
        """
        mock_redis.zpopmin.return_value = [("london", -10.0)]

        city = await queue_service.get_from_queue()

        assert city == "london"

    async def test_get_from_queue_empty(self, queue_service, mock_redis):
        """Test behavior when queue is empty.

        Verifies that attempting to retrieve from an empty queue
        returns None rather than raising an exception, allowing
        graceful handling of empty queue conditions.
        """
        mock_redis.zpopmin.return_value = []

        city = await queue_service.get_from_queue()

        assert city is None
        mock_redis.zpopmin.assert_called_once()

    async def test_get_from_queue_connection_error(self, queue_service, mock_redis):
        """Test connection error handling during queue retrieval.

        Ensures that Redis connection failures are properly
        propagated after retry attempts for appropriate
        error handling by calling code.
        """
        mock_redis.zpopmin.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await queue_service.get_from_queue()

    async def test_get_from_queue_timeout_error(self, queue_service, mock_redis):
        """Test retry behavior on Redis timeout during retrieval.

        Validates that timeout errors trigger multiple retry
        attempts before the exception is raised, demonstrating
        the resilience mechanisms in place.
        """
        mock_redis.zpopmin.side_effect = redis.TimeoutError("Timeout")

        with pytest.raises(redis.TimeoutError):
            await queue_service.get_from_queue()

        assert mock_redis.zpopmin.call_count == 3

    async def test_get_from_queue_general_error(self, queue_service, mock_redis):
        """Test non-retriable error handling during retrieval.

        Confirms that unexpected exceptions bypass retry logic
        and are immediately raised, as they likely indicate
        programming errors rather than transient issues.
        """
        mock_redis.zpopmin.side_effect = Exception("General error")

        with pytest.raises(Exception) as exc_info:
            await queue_service.get_from_queue()

        assert str(exc_info.value) == "General error"
        mock_redis.zpopmin.assert_called_once()

    async def test_get_queue_size_success(self, queue_service, mock_redis):
        """Test retrieving current queue size.

        Verifies that the service correctly queries Redis
        for the cardinality of the sorted set representing
        the queue length.
        """
        mock_redis.zcard.return_value = 5

        size = await queue_service.get_queue_size()

        assert size == 5
        mock_redis.zcard.assert_called_once_with("weather:queue:cities")

    async def test_get_queue_size_empty(self, queue_service, mock_redis):
        """Test size query for empty queue.

        Ensures that an empty queue correctly reports
        zero size without errors.
        """
        mock_redis.zcard.return_value = 0

        size = await queue_service.get_queue_size()

        assert size == 0

    async def test_get_queue_size_connection_error(self, queue_service, mock_redis):
        """Test connection failure during size query.

        Validates error propagation when Redis is unavailable
        during queue size checks.
        """
        mock_redis.zcard.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await queue_service.get_queue_size()

    async def test_get_queue_size_timeout_error(self, queue_service, mock_redis):
        """Test timeout handling with retries for size queries.

        Confirms that timeout errors trigger the retry mechanism
        before ultimately failing if Redis remains unresponsive.
        """
        mock_redis.zcard.side_effect = redis.TimeoutError("Timeout")

        with pytest.raises(redis.TimeoutError):
            await queue_service.get_queue_size()

        assert mock_redis.zcard.call_count == 3

    async def test_get_queue_size_general_error(self, queue_service, mock_redis):
        """Test non-retriable errors during size query.

        Verifies that unexpected exceptions are immediately
        raised without retry attempts.
        """
        mock_redis.zcard.side_effect = Exception("General error")

        with pytest.raises(Exception) as exc_info:
            await queue_service.get_queue_size()

        assert str(exc_info.value) == "General error"
        mock_redis.zcard.assert_called_once()

    async def test_clear_queue_success(self, queue_service, mock_redis):
        """Test successful queue clearing operation.

        Validates that the clear operation correctly deletes
        the entire queue sorted set from Redis.
        """
        mock_redis.delete.return_value = 1

        await queue_service.clear_queue()

        mock_redis.delete.assert_called_once_with("weather:queue:cities")

    async def test_clear_queue_connection_error(self, queue_service, mock_redis):
        """Test connection error during queue clearing.

        Ensures that Redis connection failures during delete
        operations are properly handled and propagated.
        """
        mock_redis.delete.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await queue_service.clear_queue()

    async def test_clear_queue_timeout_error(self, queue_service, mock_redis):
        """Test timeout with retries during queue clearing.

        Validates that the retry mechanism is triggered for
        timeout errors during delete operations, attempting
        multiple times before failure.
        """
        mock_redis.delete.side_effect = redis.TimeoutError("Timeout")

        with pytest.raises(redis.TimeoutError):
            await queue_service.clear_queue()

        assert mock_redis.delete.call_count == 3

    async def test_clear_queue_general_error(self, queue_service, mock_redis):
        """Test unexpected errors during queue clearing.

        Confirms that non-Redis exceptions bypass retry logic
        and are raised immediately to the caller.
        """
        mock_redis.delete.side_effect = Exception("General error")

        with pytest.raises(Exception) as exc_info:
            await queue_service.clear_queue()

        assert str(exc_info.value) == "General error"
        mock_redis.delete.assert_called_once()
