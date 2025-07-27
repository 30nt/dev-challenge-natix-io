"""
This module defines the routes for API version 2.
"""

from datetime import datetime, UTC

import redis.asyncio as redis
from fastapi import APIRouter, Query, Request, HTTPException, Depends

from app.config import get_settings
from app.schemas.api_v2 import (
    WeatherResponseV2,
    HealthResponse,
    MetricsResponse,
)
from app.services.dummy_external_api import dummy_weather_api
from app.services.rate_limit_service import RateLimitService
from app.services.request_stats_service import RequestStatsService
from app.services.weather_service import WeatherService
from app.definitions.data_sources import ApiVersion
from app.utils.dependencies import (
    get_weather_service,
    get_redis_client,
    get_stats_tracker,
    get_rate_limiter,
)
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()

router = APIRouter(prefix=f"/{ApiVersion.V2.value}", tags=[ApiVersion.V2.value])
default_router = APIRouter(tags=["default"])


@router.get("/weather", response_model=WeatherResponseV2)
async def get_weather_v2(
    request: Request,
    city: str = Query(..., description="City name", min_length=1, max_length=100),
    weather_service: WeatherService = Depends(get_weather_service),
) -> WeatherResponseV2:
    """
    Get weather data for a specific city (V2 API - Enhanced Format).

    Returns weather data with additional metadata and enhanced information.
    """
    try:
        weather_data = await weather_service.get_weather(city, ApiVersion.V2)
        return weather_data

    except Exception as e:
        logger.error(
            "Error getting weather",
            extra={
                "event": "api_error",
                "api_version": "v2",
                "city": city,
                "error": str(e),
                "error_type": type(e).__name__,
                "request_id": request.state.request_id,
            },
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "detail": "Failed to retrieve weather data",
                "request_id": request.state.request_id,
            },
        ) from e


@router.get("/health", response_model=HealthResponse)
async def health_check(
    request: Request,
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """
    Health check endpoint that returns service status.
    """
    redis_status = "healthy"
    try:
        await redis_client.ping()
    except Exception:
        redis_status = "unhealthy"

    circuit_status = dummy_weather_api.circuit_breaker.state

    return HealthResponse(
        status="healthy" if redis_status == "healthy" else "degraded",
        version=settings.app_version,
        timestamp=datetime.now(UTC).isoformat(),
        services={
            "redis": redis_status,
            "external_api_circuit_breaker": circuit_status,
        },
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    request: Request,
    stats_tracker: RequestStatsService = Depends(get_stats_tracker),
    rate_limiter: RateLimitService = Depends(get_rate_limiter),
):
    """
    Metrics endpoint that returns rate limit status and top requested cities.
    """
    top_cities = await stats_tracker.get_top_cities(10)
    rate_limit_remaining = await rate_limiter.get_rate_limit_remaining()

    return MetricsResponse(
        rate_limit_remaining=rate_limit_remaining,
        rate_limit_window_seconds=settings.rate_limit_window,
        circuit_breaker_status=dummy_weather_api.circuit_breaker.state,
        top_cities=[{"city": city, "requests": count} for city, count in top_cities],
    )


default_router.get("/weather", response_model=WeatherResponseV2)(get_weather_v2)
default_router.get("/health", response_model=HealthResponse)(health_check)
default_router.get("/metrics", response_model=MetricsResponse)(get_metrics)
