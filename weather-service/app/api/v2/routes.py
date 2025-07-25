from datetime import datetime, UTC

from fastapi import APIRouter, Query, Request, HTTPException, Depends

from app.config import get_settings
from app.middleware.dependency_container import container
from app.schemas.api_v2 import (
    WeatherResponseV2,
    WeatherMetadata,
    HealthResponse,
    MetricsResponse,
)
from app.services.external_api import weather_api_client
from app.services.weather_service import WeatherService
from app.utils.logger import setup_logger

VERSION = "v2"

logger = setup_logger(__name__)
settings = get_settings()

router = APIRouter(prefix=f"/{VERSION}", tags=[VERSION])


def get_weather_service() -> WeatherService:
    return container.weather_service


@router.get("/weather", response_model=WeatherResponseV2)
async def get_weather_v2(
        request: Request,
        city: str = Query(..., description="City name", min_length=1, max_length=100),
        weather_service: WeatherService = Depends(get_weather_service)
) -> WeatherResponseV2:
    """
    Get weather data for a specific city (V2 API - Enhanced Format).
    
    Returns weather data with additional metadata and enhanced information.
    """
    try:
        logger.info(f"V2 API request for city: {city}")

        weather_data = await weather_service.get_weather(city)

        # Convert to V2 format with temperature as string
        v2_response = WeatherResponseV2(
            city=weather_data.city,
            date=weather_data.date,
            weather=[
                {
                    "hour": hour.hour,
                    "temperature": str(hour.temperature),
                    "temperature_unit": hour.temperature_unit,
                    "condition": hour.condition,
                    "feels_like": hour.feels_like,
                    "humidity": hour.humidity,
                    "wind_speed": hour.wind_speed,
                    "wind_direction": hour.wind_direction
                }
                for hour in weather_data.weather
            ],
            metadata=WeatherMetadata(
                last_updated=weather_data.metadata.last_updated,
                data_freshness=weather_data.metadata.data_freshness,
                source=weather_data.metadata.source
            ),
            warnings=weather_data.warnings
        )

        return v2_response

    except Exception as e:
        logger.error(f"Error getting weather for {city}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "detail": "Failed to retrieve weather data",
                "request_id": request.state.request_id
            }
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    cache_service = request.app.state.cache_service

    redis_status = "healthy"
    try:
        await cache_service.redis_client.ping()
    except:
        redis_status = "unhealthy"

    circuit_status = weather_api_client.get_circuit_breaker_status()

    return HealthResponse(
        status="healthy" if redis_status == "healthy" else "degraded",
        version=settings.app_version,
        timestamp=datetime.now(UTC).isoformat(),
        services={
            "redis": redis_status,
            "external_api_circuit_breaker": circuit_status
        }
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(request: Request):
    cache_service = request.app.state.cache_service

    top_cities = await cache_service.get_top_cities(10)
    rate_limit_remaining = await cache_service.get_rate_limit_remaining()

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
        circuit_breaker_status=weather_api_client.get_circuit_breaker_status(),
        top_cities=[
            {"city": city, "requests": count}
            for city, count in top_cities
        ]
    )
