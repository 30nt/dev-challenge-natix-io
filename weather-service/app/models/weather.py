from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List, Optional

from app.definitions.data_sources import DataSource, DataFreshness, TemperatureUnit, WeatherCondition, \
    VALID_WIND_DIRECTIONS


class HourlyWeather(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    temperature: int = Field(..., description="Temperature value")
    temperature_unit: TemperatureUnit = Field(default="celsius")
    condition: str = Field(..., description="Weather condition")
    feels_like: Optional[int] = Field(None, description="Feels like temperature")
    humidity: Optional[int] = Field(None, ge=0, le=100, description="Humidity percentage")
    wind_speed: Optional[int] = Field(None, ge=0, description="Wind speed in km/h")
    wind_direction: Optional[str] = Field(None, description="Wind direction (N, NE, E, SE, S, SW, W, NW)")
    
    @field_validator('condition')
    @classmethod
    def validate_condition(cls, v: str) -> str:
        valid_conditions = [c.value for c in WeatherCondition]
        if v not in valid_conditions:
            pass
        return v
    
    @field_validator('wind_direction')
    @classmethod
    def validate_wind_direction(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in VALID_WIND_DIRECTIONS:
            raise ValueError(f'Invalid wind direction. Must be one of: {", ".join(VALID_WIND_DIRECTIONS)}')
        return v


class WeatherMetadata(BaseModel):
    last_updated: datetime = Field(..., description="Last update timestamp")
    data_freshness: DataFreshness = Field(..., description="Data freshness indicator")
    cache_ttl_seconds: int = Field(..., description="Cache TTL in seconds")
    source: DataSource = Field(..., description="Data source")


class ExternalAPIWeatherResponse(BaseModel):
    result: List[dict] = Field(..., description="Weather data from external API")


class WeatherResponse(BaseModel):
    city: str = Field(..., description="City name")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    weather: List[HourlyWeather] = Field(..., description="Hourly weather data")
    metadata: WeatherMetadata = Field(..., description="Response metadata")
    warnings: List[str] = Field(default_factory=list, description="Any warnings about the data")


class CityStats(BaseModel):
    city: str
    request_count: int = 0
    last_requested: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
    request_id: Optional[str] = Field(None, description="Request tracking ID")