from app.schemas.api_v2 import WeatherResponseV2, HourlyWeatherV2, WeatherMetadata
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class WeatherCRUDV2:
    """
    CRUD operations for V2 weather API responses.

    Transforms internal weather data to V2 format which includes:
    - Enhanced weather data with metadata
    - Temperature
    - Additional weather parameters (feels_like, humidity, wind)
    - Warnings and metadata information
    """

    @staticmethod
    def transform_internal(internal_data) -> WeatherResponseV2:
        """
        Transform internal weather response to V2 API format.
        """
        weather_data = []
        for hour_data in internal_data.weather:
            hour = HourlyWeatherV2(
                hour=hour_data.hour,
                temperature=str(hour_data.temperature),
                temperature_unit=hour_data.temperature_unit,
                condition=hour_data.condition,
                feels_like=hour_data.feels_like,
                humidity=hour_data.humidity,
                wind_speed=hour_data.wind_speed,
                wind_direction=hour_data.wind_direction,
            )
            weather_data.append(hour)

        response = WeatherResponseV2(
            city=internal_data.city,
            date=internal_data.date,
            weather=weather_data,
            metadata=WeatherMetadata(
                last_updated=internal_data.metadata.last_updated,
                data_freshness=internal_data.metadata.data_freshness,
                source=internal_data.metadata.source,
            ),
            warnings=internal_data.warnings,
        )

        return response
