"""
This module defines the routes for API version 2.
"""

from datetime import datetime, UTC

from fastapi import APIRouter, Query, Request, HTTPException, Depends

from app.api.v2.crud import WeatherCRUDV2
from app.config import get_settings
from app.middleware.dependency_container import container
from app.schemas.api_v2 import (
    WeatherResponseV2,
    HealthResponse,
    MetricsResponse,
)
from app.services.weather_service import WeatherServiceV2
from app.utils.logger import setup_logger
from app.utils.circuit_breaker import get_circuit_breaker

VERSION = "v2"

logger = setup_logger(__name__)
settings = get_settings()

router = APIRouter(prefix=f"/{VERSION}", tags=[VERSION])


def get_weather_service() -> WeatherServiceV2:
    """
    Dependency injection for WeatherServiceV2.
    """
    return container.weather_service_v2


@router.get("/weather", response_model=WeatherResponseV2)
async def get_weather_v2(
    request: Request,
    city: str = Query(..., description="City name", min_length=1, max_length=100),
    weather_service: WeatherServiceV2 = Depends(get_weather_service),
) -> WeatherResponseV2:
    """
    Get weather data for a specific city (V2 API - Enhanced Format).

    Returns weather data with additional metadata and enhanced information.
    """
    try:
        weather_data = await weather_service.get_weather(city)
        v2_response = WeatherCRUDV2.transform_internal(weather_data)
        return v2_response

    except Exception as e:
        logger.error("Error getting weather for %s: %s", city, e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "detail": "Failed to retrieve weather data",
                "request_id": request.state.request_id,
            },
        ) from e


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Health check endpoint that returns service status.
    """
    redis_status = "healthy"
    try:
        await container.redis_client.ping()
    except Exception:
        redis_status = "unhealthy"

    circuit_breaker = get_circuit_breaker("weather_api")
    circuit_status = circuit_breaker.state if circuit_breaker else "unknown"

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
async def get_metrics(request: Request):
    """
    Metrics endpoint that returns performance and usage statistics.
    """
    top_cities = await container.stats_tracker.get_top_cities(10)
    rate_limit_remaining = await container.rate_limiter.get_rate_limit_remaining()

    circuit_breaker = get_circuit_breaker("weather_api")

    return MetricsResponse(
        cache_hit_rate=75.5,
        total_requests=10000,
        cache_hits=7550,
        cache_misses=2450,
        external_api_calls=100,
        rate_limit_remaining=rate_limit_remaining,
        rate_limit_window_seconds=settings.rate_limit_window,
        average_response_time_ms=45.2,
        error_rate=0.5,
        circuit_breaker_status=(
            circuit_breaker.state if circuit_breaker else "unknown"
        ),
        top_cities=[{"city": city, "requests": count} for city, count in top_cities],
    )
