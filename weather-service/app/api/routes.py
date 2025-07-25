from datetime import datetime, UTC

from fastapi import APIRouter, Query, Request, HTTPException
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.responses import HealthResponse, MetricsResponse
from app.models.weather import WeatherResponse
from app.services.external_api import weather_api_client
from app.services.weather_service import WeatherService
from app.utils.logger import setup_logger
from app.exceptions import RateLimitExceededException

logger = setup_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.get("/weather", response_model=WeatherResponse)
async def get_weather(
        request: Request,
        city: str = Query(..., description="City name", min_length=1, max_length=100)
):
    try:
        cache_service = request.app.state.cache_service  # type: ignore[attr-defined]
        weather_service = WeatherService(cache_service)

        response = await weather_service.get_weather(city)
        return response

    except RateLimitExceededException as e:
        logger.error(f"Rate limit exceeded for {city}: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service temporarily unavailable",
                "detail": str(e),
                "retry_after": e.retry_after,
                "request_id": request.state.request_id  # type: ignore[attr-defined]
            }
        )
    except Exception as e:
        logger.error(f"Error getting weather for {city}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "detail": "Failed to retrieve weather data",
                "request_id": request.state.request_id  # type: ignore[attr-defined]
            }
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    cache_service = request.app.state.cache_service  # type: ignore[attr-defined]

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
    cache_service = request.app.state.cache_service  # type: ignore[attr-defined]

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
