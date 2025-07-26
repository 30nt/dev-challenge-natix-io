"""
Common test fixtures and configuration.
"""

from unittest.mock import patch, MagicMock

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def fast_retry_settings():
    """
    Override retry settings for faster test execution.

    This fixture modifies retry delays to milliseconds instead of seconds,
    allowing tests to complete quickly while still exercising retry logic.
    The original retry behavior (3 attempts with exponential backoff) is
    preserved, just with much shorter delays.

    Yields:
        MagicMock: Settings object with fast retry configuration
    """

    real_settings = get_settings()

    mock_settings = MagicMock()

    for attr in dir(real_settings):
        if not attr.startswith("_"):
            setattr(mock_settings, attr, getattr(real_settings, attr))

    mock_settings.retry_max_attempts = 3
    mock_settings.retry_wait_random_min = 0.01
    mock_settings.retry_wait_random_max = 0.02

    with patch("app.utils.resilience.settings", mock_settings):
        yield mock_settings
