"""
This module defines schemas for API version 2.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import Field, field_validator, BaseModel

from app.definitions.data_sources import (
    TemperatureUnit,
    WindDirections,
    DataFreshness,
    DataSource,
)
from app.exceptions.common import ValidationError
from app.schemas.common import BaseHourlyWeather


class WeatherMetadata(BaseModel):
    """
    V2 weather metadata model.
    """

    last_updated: datetime = Field(..., description="Last update timestamp")
    data_freshness: DataFreshness = Field(..., description="Data freshness indicator")
    source: DataSource = Field(..., description="Data source")


class HourlyWeatherV2(BaseHourlyWeather):
    """
    V2 weather hour data model with enhanced information.
    Extends BaseWeatherHour with additional weather metrics and metadata.
    Provides comprehensive weather information for better user experience.
    """

    temperature_unit: TemperatureUnit = Field(default="celsius")
    feels_like: Optional[int] = Field(None, description="Feels like temperature")
    humidity: Optional[int] = Field(
        None, ge=0, le=100, description="Humidity percentage"
    )
    wind_speed: Optional[int] = Field(None, ge=0, description="Wind speed in km/h")
    wind_direction: Optional[str] = Field(
        None, description="Wind direction (N, NE, E, SE, S, SW, W, NW)"
    )

    @field_validator("wind_direction")
    @classmethod
    def validate_wind_direction(cls, v: Optional[str]) -> Optional[str]:
        wind_direction = [c.value for c in WindDirections]
        if v and v not in wind_direction:
            raise ValidationError(
                f'Invalid wind direction. Must be one of: {", ".join(wind_direction)}'
            )
        return v


class WeatherResponseV2(BaseModel):
    """
    V2 API response model for weather data.
    Enhanced format with comprehensive weather information and metadata.
    Provides detailed hourly weather data with additional context for better UX.
    """

    city: str = Field(..., description="City name")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    weather: List[HourlyWeatherV2] = Field(..., description="Hourly weather data")
    metadata: WeatherMetadata = Field(..., description="Response metadata")
    warnings: List[str] = Field(
        default_factory=list, description="Any warnings about the data"
    )


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")
    services: Dict[str, str] = Field(..., description="Status of dependent services")


class MetricsResponse(BaseModel):
    cache_hit_rate: float = Field(..., description="Cache hit rate percentage")
    total_requests: int = Field(..., description="Total number of requests")
    cache_hits: int = Field(..., description="Number of cache hits")
    cache_misses: int = Field(..., description="Number of cache misses")
    external_api_calls: int = Field(..., description="Number of external API calls")
    rate_limit_remaining: int = Field(
        ..., description="Remaining API calls in current window"
    )
    rate_limit_window_seconds: int = Field(
        ..., description="Rate limit window duration"
    )
    average_response_time_ms: float = Field(
        ..., description="Average response time in milliseconds"
    )
    error_rate: float = Field(..., description="Error rate percentage")
    circuit_breaker_status: str = Field(..., description="Circuit breaker status")
    top_cities: list[Dict[str, Any]] = Field(..., description="Most requested cities")
