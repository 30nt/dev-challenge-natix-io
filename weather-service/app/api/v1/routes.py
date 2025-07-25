from fastapi import APIRouter, Query, Depends, HTTPException

from app.middleware.dependency_container import container
from app.schemas.api_v1 import WeatherResponse
from app.services.weather_service import WeatherService
from app.utils.logger import setup_logger

VERSION = "v1"

logger = setup_logger(__name__)

router = APIRouter(prefix=f"/{VERSION}", tags=[VERSION])


def get_weather_service() -> WeatherService:
    return container.weather_service


@router.get("/weather", response_model=WeatherResponse)
async def get_weather_v1(
        city: str = Query(..., description="City name", min_length=1, max_length=100),
        weather_service: WeatherService = Depends(get_weather_service)
) -> WeatherResponse:
    """
    Get weather data for a specific city (V1 API - Simple Format).
    
    Returns weather data in the original challenge format with temperature as string including unit.
    """
    try:
        logger.info(f"V1 API request for city: {city}")

        weather_data = await weather_service.get_weather(city)

        v1_response = WeatherResponse(
            weather=[
                {
                    "hour": hour.hour,
                    "temperature": f"{hour.temperature}°C",
                    "condition": hour.condition
                }
                for hour in weather_data.weather
            ]
        )

        return v1_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in V1 weather endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
