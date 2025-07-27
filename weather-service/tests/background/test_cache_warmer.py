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
    """Test suite for background cache warming functionality.

    Validates the cache warmer's ability to proactively refresh
    weather data for popular cities during low-traffic periods.
    """

    @pytest.mark.asyncio
    async def test_warm_single_city_success(self):
        """Test successful cache warming for individual city.

        Verifies that the cache warmer correctly calls the weather
        service to refresh data for a specified city using the V2 API.
        """
        weather_service = AsyncMock()
        semaphore = asyncio.Semaphore(1)

        await warm_single_city("London", weather_service, semaphore)

        weather_service.get_weather.assert_called_once_with("London", ApiVersion.V2)

    @pytest.mark.asyncio
    async def test_get_cities_to_warm_with_stats(self):
        """Test city selection based on request statistics.

        Validates that the cache warmer prioritizes cities by
        request frequency and filters out already-cached entries
        to optimize rate limit token usage.
        """
        stats_tracker = AsyncMock()
        stats_tracker.get_top_cities.return_value = [
            ("London", 100),
            ("Paris", 80),
            ("Tokyo", 60),
            ("New York", 40),
        ]

        weather_cache = AsyncMock()
        weather_cache.get_weather.side_effect = [None, None, "cached", "cached"]

        cities = await get_cities_to_warm(stats_tracker, weather_cache, 3)

        assert len(cities) == 3
        assert cities[0][0] == "London"
        assert cities[1][0] == "Paris"
        assert cities[2][0] == "Tokyo"

    @pytest.mark.asyncio
    async def test_get_cities_to_warm_no_stats(self):
        """Test fallback behavior when no statistics exist.

        Ensures the cache warmer uses default city list when
        request statistics are unavailable, typically during
        initial deployment or after stats reset.
        """
        stats_tracker = AsyncMock()
        stats_tracker.get_top_cities.return_value = []
        weather_cache = AsyncMock()

        cities = await get_cities_to_warm(stats_tracker, weather_cache, 3)

        assert len(cities) == 3
        assert all(count == 0 for _, count in cities)

    @pytest.mark.asyncio
    async def test_warm_cache_insufficient_tokens(self):
        """Test rate limit preservation during cache warming.

        Validates that cache warming respects minimum token
        thresholds to ensure sufficient capacity remains for
        real-time user requests.
        """
        app = MagicMock()

        with patch("app.background.cache_warmer.get_redis_pool") as mock_pool:
            mock_redis_client = AsyncMock()
            mock_pool_instance = AsyncMock()
            mock_pool_instance.get_client.return_value = mock_redis_client
            mock_pool.return_value = mock_pool_instance

            with patch(
                "app.background.cache_warmer.RateLimitService"
            ) as mock_rate_service:
                mock_rate_limiter = AsyncMock()
                mock_rate_limiter.get_rate_limit_remaining = AsyncMock(return_value=5)
                mock_rate_service.return_value = mock_rate_limiter

                with patch(
                    "app.background.cache_warmer.RequestStatsService"
                ) as mock_stats_service:
                    mock_stats_tracker = AsyncMock()
                    mock_stats_service.return_value = mock_stats_tracker

                    with patch("app.background.cache_warmer.settings") as mock_settings:
                        mock_settings.cache_warm_min_tokens_remaining = 10

                        await warm_cache(app)

                        mock_stats_tracker.get_top_cities.assert_not_called()

    @pytest.mark.asyncio
    async def test_warm_cache_concurrent_execution(self):
        """Test concurrent cache warming."""
        app = MagicMock()

        with patch("app.background.cache_warmer.get_redis_pool") as mock_pool:
            mock_redis_client = AsyncMock()
            mock_redis_client.ping = AsyncMock(return_value=b"PONG")
            mock_pool_instance = AsyncMock()
            mock_pool_instance.get_client.return_value = mock_redis_client
            mock_pool.return_value = mock_pool_instance

            with patch(
                "app.background.cache_warmer.WeatherCacheService"
            ) as mock_cache_service:
                mock_weather_cache = AsyncMock()
                mock_weather_cache.get_weather.return_value = None
                mock_cache_service.return_value = mock_weather_cache

                with patch(
                    "app.background.cache_warmer.RateLimitService"
                ) as mock_rate_service:
                    mock_rate_limiter = AsyncMock()
                    mock_rate_limiter.get_rate_limit_remaining = AsyncMock(
                        return_value=50
                    )
                    mock_rate_limiter.consume_rate_limit_token = AsyncMock(
                        return_value=True
                    )
                    mock_rate_service.return_value = mock_rate_limiter

                    with patch(
                        "app.background.cache_warmer.RequestStatsService"
                    ) as mock_stats_service:
                        mock_stats_tracker = AsyncMock()
                        mock_stats_tracker.get_top_cities.return_value = [
                            ("London", 100),
                            ("Paris", 80),
                            ("Tokyo", 60),
                        ]
                        mock_stats_service.return_value = mock_stats_tracker

                        with patch(
                            "app.background.cache_warmer.WeatherService"
                        ) as mock_weather_service_class:
                            mock_weather_service = AsyncMock()
                            mock_weather_service.get_weather.return_value = {
                                "data": "weather"
                            }
                            mock_weather_service_class.return_value = (
                                mock_weather_service
                            )

                            with patch(
                                "app.background.cache_warmer.settings"
                            ) as mock_settings:
                                mock_settings.cache_warm_min_tokens_remaining = 10
                                mock_settings.cache_warm_max_tokens = 20

                                await warm_cache(app)

                                assert mock_weather_service.get_weather.call_count == 3

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
