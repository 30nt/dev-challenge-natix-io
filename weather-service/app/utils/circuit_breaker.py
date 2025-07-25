"""
Simplified circuit breaker implementation for protecting external service calls.
"""

import asyncio
import time
from enum import Enum
from functools import wraps
from typing import Callable, Optional
from app.utils.logger import setup_logger
from app.exceptions import CircuitBreakerOpenException

logger = setup_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    A simple circuit breaker implementation for protecting external service calls.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are blocked
    - HALF_OPEN: Testing if service has recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Optional[type[Exception]] = None,
        name: str = "CircuitBreaker",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception or Exception
        self.name = name

        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> str:
        """Get current circuit breaker state as string."""
        return self._state.value

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (
            self._last_failure_time
            and time.time() - self._last_failure_time >= self.recovery_timeout
        )

    def _record_success(self):
        """Record successful call."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        logger.debug("Circuit breaker '%s' recorded success, state: CLOSED", self.name)

    def _record_failure(self):
        """Record failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker '%s' opened after %s failures",
                self.name,
                self._failure_count,
            )

    def _get_state(self) -> CircuitState:
        """Get current state, checking if we should transition to half-open."""
        if self._state == CircuitState.OPEN and self._should_attempt_reset():
            self._state = CircuitState.HALF_OPEN
            logger.debug("Circuit breaker '%s' half-open, attempting reset", self.name)
        return self._state

    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap async functions with circuit breaker protection."""
        if not asyncio.iscoroutinefunction(func):
            raise ValueError(
                f"Circuit breaker only supports async functions, got {func}"
            )

        @wraps(func)
        async def wrapper(*args, **kwargs):
            state = self._get_state()

            if state == CircuitState.OPEN:
                error_msg = f"Circuit breaker '{self.name}' is OPEN"
                logger.error(error_msg)
                raise CircuitBreakerOpenException(error_msg)

            try:
                result = await func(*args, **kwargs)
                self._record_success()
                return result
            except self.expected_exception as e:
                self._record_failure()
                raise e

        return wrapper
