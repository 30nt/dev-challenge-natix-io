"""
This module defines schemas for API version 1.
"""

from typing import List

from pydantic import BaseModel

from app.schemas.common import BaseHourlyWeather


class HourlyWeather(BaseHourlyWeather):
    """
    Weather hour data model.

    Inherits from BaseWeatherHour with hour, temperature, and condition.
    """


class WeatherResponse(BaseModel):
    """
    API response model for weather data.

    Simple format matching the original challenge specification.
    Contains only the essential weather information without metadata.
    """

    weather: List[HourlyWeather]
