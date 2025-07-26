"""
This module defines the routes for API version 1.
"""

from fastapi import APIRouter, Query, Depends, HTTPException, Response

from app.api.v1.crud import WeatherCRUD
from app.schemas.api_v1 import WeatherResponse
from app.services.weather_service import WeatherService, ApiVersion
from app.utils.dependencies import get_weather_service
from app.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter(prefix=f"/{ApiVersion.V1.value}", tags=[ApiVersion.V1.value])


@router.get("/weather", response_model=WeatherResponse, deprecated=True)
async def get_weather_v1(
    response: Response,
    city: str = Query(..., description="City name", min_length=1, max_length=100),
    weather_service: WeatherService = Depends(get_weather_service),
) -> WeatherResponse:
    """
    Get weather data for a specific city (V1 API - Simple Format).

    **DEPRECATED**: This endpoint is deprecated and will be removed in a future version.
    Please use the v2 API endpoint instead for enhanced features and metadata.

    Returns weather data in the original challenge format with temperature as
    string including unit.
    """
    try:
        response.headers["X-API-Deprecation"] = "true"
        response.headers["X-API-Deprecation-Date"] = "2024-12-31"
        response.headers["X-API-Deprecation-Info"] = "Please migrate to v2 API"

        weather_data = await weather_service.get_weather(city, ApiVersion.V1)
        return WeatherCRUD.transform_internal(weather_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error in V1 weather endpoint",
            extra={
                "event": "api_error",
                "api_version": "v1",
                "city": city,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        raise HTTPException(status_code=500, detail="Internal server error") from e
