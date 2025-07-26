"""
Tests for the circuit breaker utility.
"""

import asyncio

import pytest

from app.utils.circuit_breaker import CircuitBreaker, CircuitState
from app.exceptions import CircuitBreakerOpenException


class TestCircuitBreaker:
    """Test suite for circuit breaker pattern implementation.

    Validates state transitions, failure detection, and recovery
    mechanisms for protecting external service calls.
    """

    def test_initial_state(self):
        """Test circuit breaker initialization in closed state.

        Verifies that new circuit breakers start in the closed state,
        allowing normal operation with zero failure count.
        """
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)

        assert cb.state == CircuitState.CLOSED.value
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_successful_calls(self):
        """Test circuit remains closed during successful operations.

        Validates that consecutive successful calls keep the circuit
        closed and reset any previous failure counts, allowing
        continuous normal operation.
        """
        cb = CircuitBreaker(failure_threshold=3)

        @cb
        async def successful_operation():
            return "success"

        for _ in range(5):
            result = await successful_operation()
            assert result == "success"

        assert cb.state == CircuitState.CLOSED.value
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self):
        """Test circuit opening after consecutive failures.

        Verifies that the circuit breaker transitions to open state
        after the failure threshold is reached, blocking subsequent
        calls to protect the failing service from overload.
        """
        cb = CircuitBreaker(failure_threshold=3, expected_exception=ValueError)

        @cb
        async def failing_operation():
            raise ValueError("Test failure")

        for _ in range(3):
            with pytest.raises(ValueError):
                await failing_operation()

        assert cb.state == CircuitState.OPEN.value
        assert cb._failure_count == 3

        with pytest.raises(CircuitBreakerOpenException):
            await failing_operation()

    @pytest.mark.asyncio
    async def test_circuit_half_open_after_timeout(self):
        """Test recovery attempt after timeout period.

        Validates the half-open state mechanism where the circuit
        allows a test request after the recovery timeout. Success
        closes the circuit, while failure would reopen it.
        """
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

        @cb
        async def operation(should_fail=True):
            if should_fail:
                raise ValueError("Test failure")
            return "success"

        for _ in range(2):
            with pytest.raises(ValueError):
                await operation()

        assert cb.state == CircuitState.OPEN.value

        await asyncio.sleep(1.1)

        result = await operation(should_fail=False)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED.value

    def test_decorator_usage(self):
        """Test circuit breaker decorator functionality.

        Ensures the circuit breaker can be used as a decorator
        without affecting the wrapped function's behavior during
        normal operation.
        """
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=30, name="test_breaker"
        )

        @cb
        async def decorated_operation():
            return "success"

        assert asyncio.run(decorated_operation()) == "success"

    def test_sync_function_wrapper(self):
        """Test circuit breaker validation for async-only support.

        Verifies that attempting to decorate synchronous functions
        raises an appropriate error, as the circuit breaker is
        designed specifically for async operations.
        """
        cb = CircuitBreaker(failure_threshold=2)

        with pytest.raises(
            ValueError, match="Circuit breaker only supports async functions"
        ):

            @cb
            def sync_operation():
                return "sync_success"
