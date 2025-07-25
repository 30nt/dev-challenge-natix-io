from app.schemas.api_v1 import WeatherResponse, HourlyWeather
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class WeatherCRUD:

    @staticmethod
    def transform_internal(internal_data) -> WeatherResponse:
        """
        Transform internal weather response to API format.
        """
        weather_data = []
        for hour_data in internal_data.weather:
            hour = HourlyWeather(
                hour=hour_data.hour,
                temperature=str(hour_data.temperature),
                condition=hour_data.condition,
            )
            weather_data.append(hour)

        response = WeatherResponse(weather=weather_data)

        return response
