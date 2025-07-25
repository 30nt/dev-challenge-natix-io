from pydantic import BaseModel, Field, field_validator

from app.definitions.data_sources import WeatherCondition
from app.exceptions.common import ValidationError


class BaseHourlyWeather(BaseModel):
    """
    Base model for hourly weather data.

    Common fields shared between all API versions and internal processing.
    Provides the foundation for version-specific weather hour models.

    Attributes:
        hour: Hour of the day (0-23)
        temperature: Temperature value as string
        condition: Weather condition (e.g., 'Clear', 'Cloudy', 'Rainy')
    """

    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    temperature: str = Field(..., description="Temperature value")
    condition: str = Field(..., description="Weather condition")

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: str) -> str:
        valid_conditions = [c.value for c in WeatherCondition]
        if v not in valid_conditions:
            raise ValidationError(
                message=f'Invalid weather condition. Must be one of: {", ".join(valid_conditions)}'
            )
        return v
