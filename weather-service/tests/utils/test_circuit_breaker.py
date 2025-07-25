"""
Tests for the circuit breaker utility.
"""

import asyncio

import pytest

from app.utils.circuit_breaker import CircuitBreaker, CircuitState, circuit_breaker
from app.exceptions import CircuitBreakerOpenException


class TestCircuitBreaker:
    """Test cases for the circuit breaker."""

    def test_initial_state(self):
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        assert cb.state == CircuitState.CLOSED.value
        assert cb._failure_count == 0  # pylint: disable=protected-access

    @pytest.mark.asyncio
    async def test_successful_calls(self):
        """Test circuit breaker with successful calls."""
        cb = CircuitBreaker(failure_threshold=3)

        @cb
        async def successful_operation():
            return "success"

        # Multiple successful calls should keep circuit closed
        for _ in range(5):
            result = await successful_operation()
            assert result == "success"

        assert cb.state == CircuitState.CLOSED.value
        assert cb._failure_count == 0  # pylint: disable=protected-access

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3, expected_exception=ValueError)

        @cb
        async def failing_operation():
            raise ValueError("Test failure")

        # Fail 3 times to open the circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await failing_operation()

        assert cb.state == CircuitState.OPEN.value
        assert cb._failure_count == 3  # pylint: disable=protected-access

        # Next call should raise CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            await failing_operation()

    @pytest.mark.asyncio
    async def test_circuit_half_open_after_timeout(self):
        """Test circuit transitions to half-open after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        @cb
        async def operation(should_fail=True):
            if should_fail:
                raise ValueError("Test failure")
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await operation()

        assert cb.state == CircuitState.OPEN.value

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Circuit should attempt half-open on next call
        # Successful call should close the circuit
        result = await operation(should_fail=False)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED.value

    def test_decorator_factory(self):
        """Test circuit breaker decorator factory."""

        @circuit_breaker(failure_threshold=2, recovery_timeout=30, name="test_breaker")
        async def decorated_operation():
            return "success"

        # The decorated function should work normally
        assert asyncio.run(decorated_operation()) == "success"

    def test_sync_function_wrapper(self):
        """Test circuit breaker with synchronous functions."""
        cb = CircuitBreaker(failure_threshold=2)

        @cb
        def sync_operation():
            return "sync_success"

        # Should work with sync functions
        result = sync_operation()
        assert result == "sync_success"
