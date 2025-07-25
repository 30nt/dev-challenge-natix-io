"""
Tests for the queue service module.
"""

from unittest.mock import AsyncMock

import pytest
import redis.asyncio as redis

from app.services.queue_service import QueueService


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    return AsyncMock()


@pytest.fixture
def queue_service(mock_redis):
    """Create a QueueService instance with mocked Redis."""
    return QueueService(mock_redis)


class TestQueueService:
    """Test cases for QueueService."""

    async def test_add_to_queue_success(self, queue_service, mock_redis):
        """Test successfully adding a city to the queue."""
        mock_redis.zadd.return_value = 1

        await queue_service.add_to_queue("London", priority=5)

        mock_redis.zadd.assert_called_once_with("weather:queue:cities", {"london": -5})

    async def test_add_to_queue_default_priority(self, queue_service, mock_redis):
        """Test adding to queue with default priority."""
        mock_redis.zadd.return_value = 1

        await queue_service.add_to_queue("London")

        mock_redis.zadd.assert_called_once_with("weather:queue:cities", {"london": 0})

    async def test_add_to_queue_connection_error(self, queue_service, mock_redis):
        """Test handling connection error when adding to queue."""
        mock_redis.zadd.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await queue_service.add_to_queue("London", priority=5)

    async def test_add_to_queue_timeout_error(self, queue_service, mock_redis):
        """Test handling timeout error when adding to queue."""
        mock_redis.zadd.side_effect = redis.TimeoutError("Timeout")

        await queue_service.add_to_queue("London", priority=5)

        mock_redis.zadd.assert_called_once()

    async def test_add_to_queue_general_error(self, queue_service, mock_redis):
        """Test handling general error when adding to queue."""
        mock_redis.zadd.side_effect = Exception("General error")

        await queue_service.add_to_queue("London", priority=5)

        mock_redis.zadd.assert_called_once()

    async def test_get_from_queue_success(self, queue_service, mock_redis):
        """Test getting the next city from queue."""

        mock_redis.zpopmin.return_value = [(b"london", -10.0)]

        city = await queue_service.get_from_queue()

        assert city == "london"
        mock_redis.zpopmin.assert_called_once_with("weather:queue:cities")

    async def test_get_from_queue_string_result(self, queue_service, mock_redis):
        """Test getting from queue when result is already string."""
        mock_redis.zpopmin.return_value = [("london", -10.0)]

        city = await queue_service.get_from_queue()

        assert city == "london"

    async def test_get_from_queue_empty(self, queue_service, mock_redis):
        """Test getting next from empty queue."""
        mock_redis.zpopmin.return_value = []

        city = await queue_service.get_from_queue()

        assert city is None
        mock_redis.zpopmin.assert_called_once()

    async def test_get_from_queue_connection_error(self, queue_service, mock_redis):
        """Test handling connection error in get_from_queue."""
        mock_redis.zpopmin.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await queue_service.get_from_queue()

    async def test_get_from_queue_timeout_error(self, queue_service, mock_redis):
        """Test handling timeout error in get_from_queue."""
        mock_redis.zpopmin.side_effect = redis.TimeoutError("Timeout")

        city = await queue_service.get_from_queue()

        assert city is None

    async def test_get_from_queue_general_error(self, queue_service, mock_redis):
        """Test handling general error in get_from_queue."""
        mock_redis.zpopmin.side_effect = Exception("General error")

        city = await queue_service.get_from_queue()

        assert city is None

    async def test_get_queue_size_success(self, queue_service, mock_redis):
        """Test getting queue size."""
        mock_redis.zcard.return_value = 5

        size = await queue_service.get_queue_size()

        assert size == 5
        mock_redis.zcard.assert_called_once_with("weather:queue:cities")

    async def test_get_queue_size_empty(self, queue_service, mock_redis):
        """Test getting size of empty queue."""
        mock_redis.zcard.return_value = 0

        size = await queue_service.get_queue_size()

        assert size == 0

    async def test_get_queue_size_connection_error(self, queue_service, mock_redis):
        """Test handling connection error in get_queue_size."""
        mock_redis.zcard.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await queue_service.get_queue_size()

    async def test_get_queue_size_timeout_error(self, queue_service, mock_redis):
        """Test handling timeout error in get_queue_size."""
        mock_redis.zcard.side_effect = redis.TimeoutError("Timeout")

        size = await queue_service.get_queue_size()

        assert size == 0

    async def test_get_queue_size_general_error(self, queue_service, mock_redis):
        """Test handling general error in get_queue_size."""
        mock_redis.zcard.side_effect = Exception("General error")

        size = await queue_service.get_queue_size()

        assert size == 0

    async def test_clear_queue_success(self, queue_service, mock_redis):
        """Test clearing the entire queue."""
        mock_redis.delete.return_value = 1

        await queue_service.clear_queue()

        mock_redis.delete.assert_called_once_with("weather:queue:cities")

    async def test_clear_queue_connection_error(self, queue_service, mock_redis):
        """Test handling connection error in clear_queue."""
        mock_redis.delete.side_effect = redis.ConnectionError("Connection failed")

        with pytest.raises(redis.ConnectionError):
            await queue_service.clear_queue()

    async def test_clear_queue_timeout_error(self, queue_service, mock_redis):
        """Test handling timeout error in clear_queue."""
        mock_redis.delete.side_effect = redis.TimeoutError("Timeout")

        await queue_service.clear_queue()

        mock_redis.delete.assert_called_once()

    async def test_clear_queue_general_error(self, queue_service, mock_redis):
        """Test handling general error in clear_queue."""
        mock_redis.delete.side_effect = Exception("General error")

        await queue_service.clear_queue()

        mock_redis.delete.assert_called_once()
