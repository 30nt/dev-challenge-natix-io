"""
Tests for the cache warmer module.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.background.cache_warmer import (
    warm_single_city,
    get_cities_to_warm,
    warm_cache,
    cache_warmer_task,
    start_cache_warmer,
)
from app.definitions.data_sources import ApiVersion


class TestCacheWarmer:
    """Test cases for cache warmer functionality."""

    @pytest.mark.asyncio
    async def test_warm_single_city_success(self):
        """Test successful cache warming for a single city."""
        weather_service = AsyncMock()
        semaphore = asyncio.Semaphore(1)

        await warm_single_city("London", weather_service, semaphore)

        weather_service.get_weather.assert_called_once_with("London", ApiVersion.V2)

    @pytest.mark.asyncio
    async def test_get_cities_to_warm_with_stats(self):
        """Test getting cities to warm with statistics available."""
        stats_tracker = AsyncMock()
        stats_tracker.get_top_cities.return_value = [
            ("London", 100),
            ("Paris", 80),
            ("Tokyo", 60),
            ("New York", 40),
        ]

        with patch("app.background.cache_warmer.container") as mock_container:
            mock_cache = AsyncMock()
            mock_cache.get_weather.side_effect = [None, None, "cached", "cached"]
            mock_container.weather_cache = mock_cache

            cities = await get_cities_to_warm(stats_tracker, 3)

            assert len(cities) == 3
            assert cities[0][0] == "London"
            assert cities[1][0] == "Paris"
            assert cities[2][0] == "Tokyo"

    @pytest.mark.asyncio
    async def test_get_cities_to_warm_no_stats(self):
        """Test getting cities to warm without statistics."""
        stats_tracker = AsyncMock()
        stats_tracker.get_top_cities.return_value = []

        cities = await get_cities_to_warm(stats_tracker, 3)

        assert len(cities) == 3
        assert all(count == 0 for _, count in cities)

    @pytest.mark.asyncio
    async def test_warm_cache_insufficient_tokens(self):
        """Test cache warming with insufficient tokens."""
        app = MagicMock()

        with patch("app.background.cache_warmer.container") as mock_container:
            mock_container.rate_limiter.get_rate_limit_remaining.return_value = 5

            with patch("app.background.cache_warmer.settings") as mock_settings:
                mock_settings.cache_warm_min_tokens_remaining = 10

                await warm_cache(app)

                mock_container.stats_tracker.get_top_cities.assert_not_called()

    @pytest.mark.asyncio
    async def test_warm_cache_concurrent_execution(self):
        """Test concurrent cache warming."""
        app = MagicMock()

        with patch("app.background.cache_warmer.container") as mock_container:
            mock_container.rate_limiter = AsyncMock()
            mock_container.rate_limiter.get_rate_limit_remaining.return_value = 50
            mock_container.rate_limiter.consume_rate_limit_token.return_value = True
            mock_container.stats_tracker = AsyncMock()
            mock_container.stats_tracker.get_top_cities.return_value = [
                ("London", 100),
                ("Paris", 80),
                ("Tokyo", 60),
            ]
            mock_container.weather_cache = AsyncMock()
            mock_container.weather_cache.get_weather.return_value = None
            mock_container.weather_service = AsyncMock()
            mock_container.weather_service.get_weather.return_value = {
                "data": "weather"
            }

            with patch("app.background.cache_warmer.settings") as mock_settings:
                mock_settings.cache_warm_min_tokens_remaining = 10
                mock_settings.cache_warm_max_tokens = 20

                await warm_cache(app)

                assert mock_container.weather_service.get_weather.call_count == 3

    @pytest.mark.asyncio
    async def test_cache_warmer_task_cancellation(self):
        """Test cache warmer task cancellation."""
        app = MagicMock()

        with patch("app.background.cache_warmer.warm_cache"):
            task = asyncio.create_task(cache_warmer_task(app))
            await asyncio.sleep(0.1)
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_start_cache_warmer_disabled(self):
        """Test starting cache warmer when disabled."""
        app = MagicMock()

        with patch("app.background.cache_warmer.settings") as mock_settings:
            mock_settings.enable_cache_warming = False

            task = await start_cache_warmer(app)

            assert task is None

    @pytest.mark.asyncio
    async def test_start_cache_warmer_enabled(self):
        """Test starting cache warmer when enabled."""
        app = MagicMock()

        with patch("app.background.cache_warmer.settings") as mock_settings:
            mock_settings.enable_cache_warming = True

            task = await start_cache_warmer(app)

            assert task is not None
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task
