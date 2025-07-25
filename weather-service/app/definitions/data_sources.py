from enum import Enum
from typing import Literal, List

DataSource = Literal["cache", "api"]
DataFreshness = Literal["fresh", "stale"]
TemperatureUnit = Literal["celsius", "fahrenheit"]

VALID_WIND_DIRECTIONS: List[str] = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

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
    "Toronto"
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
