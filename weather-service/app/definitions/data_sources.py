"""
This module defines data sources for the application.
"""

from enum import Enum
from typing import Literal, List

DataSource = Literal["cache", "api"]
DataFreshness = Literal["fresh", "stale"]
TemperatureUnit = Literal["celsius", "fahrenheit"]

DEFAULT_CITIES: List[str] = [
    "London",
    "New York",
    "Tokyo",
    "Paris",
    "Berlin",
    "Sydney",
    "Mumbai",
    "Singapore",
    "Dubai",
    "Toronto",
]


class WeatherCondition(str, Enum):
    """Enumeration of possible weather conditions."""

    CLEAR = "Clear"
    CLOUDY = "Cloudy"
    PARTLY_CLOUDY = "Partly Cloudy"
    RAINY = "Rainy"
    STORMY = "Stormy"
    SNOWY = "Snowy"
    FOGGY = "Foggy"
    WINDY = "Windy"


class WindDirections(str, Enum):
    """Enumeration of possible wind directions."""

    N = "N"
    NE = "NE"
    E = "E"
    SE = "SE"
    S = "S"
    SW = "SW"
    W = "W"
    NW = "NW"
