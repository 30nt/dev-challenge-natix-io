import httpx
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import get_settings
from app.models.weather import ExternalAPIWeatherResponse
from app.definitions.data_sources import WeatherCondition
from app.utils.logger import setup_logger
from app.utils.circuit_breaker import circuit_breaker, get_circuit_breaker

logger = setup_logger(__name__)
settings = get_settings()


class WeatherAPIClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=settings.weather_api_timeout)
    
    async def close(self):
        await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
    )
    async def fetch_weather(self, city: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._fetch_with_circuit_breaker(city)
        except Exception as e:
            logger.error(f"Failed to fetch weather for {city}: {e}")
            raise
    
    @circuit_breaker(
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout=settings.circuit_breaker_recovery_timeout,
        name="WeatherAPI"
    )
    async def _fetch_with_circuit_breaker(self, city: str) -> Optional[Dict[str, Any]]:
        try:
            response = await self.client.get(
                settings.weather_api_url,
                params={"city": city}
            )
            response.raise_for_status()
            
            data = response.json()
            validated_response = ExternalAPIWeatherResponse(**data)
            
            return self._transform_external_response(validated_response.result)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                logger.error(f"Server error from weather API: {e}")
                raise
            else:
                logger.warning(f"Client error from weather API: {e}")
                return None
        except Exception as e:
            logger.error(f"Unexpected error fetching weather: {e}")
            raise
    
    def _normalize_condition(self, condition: str) -> str:
        """Normalize weather condition to match WeatherCondition enum values."""
        if not condition:
            return WeatherCondition.CLEAR.value
        
        valid_conditions = {c.value.lower(): c.value for c in WeatherCondition}
        condition_lower = condition.lower()
        
        if condition_lower in valid_conditions:
            return valid_conditions[condition_lower]
        
        condition_mapping = {
            "sun": WeatherCondition.CLEAR.value,
            "cloud": WeatherCondition.CLOUDY.value,
            "rain": WeatherCondition.RAINY.value,
            "storm": WeatherCondition.STORMY.value,
            "snow": WeatherCondition.SNOWY.value,
            "fog": WeatherCondition.FOGGY.value,
            "wind": WeatherCondition.WINDY.value,
            "partly": WeatherCondition.PARTLY_CLOUDY.value,
        }
        
        for key, value in condition_mapping.items():
            if key in condition_lower:
                return value
        
        logger.warning(f"Unknown weather condition '{condition}', defaulting to Clear")
        return WeatherCondition.CLEAR.value
    
    def _transform_external_response(self, external_data: list) -> Dict[str, Any]:
        weather_data = []
        
        for hour_data in external_data:
            temperature_str = hour_data.get("temperature", "0°C")
            temperature = int(temperature_str.replace("°C", "").replace("°F", ""))
            
            raw_condition = hour_data.get("condition", "Unknown")
            normalized_condition = self._normalize_condition(raw_condition)
            
            weather_data.append({
                "hour": hour_data.get("hour", 0),
                "temperature": temperature,
                "temperature_unit": "celsius",
                "condition": normalized_condition,
                "feels_like": temperature - 2,
                "humidity": 65,
                "wind_speed": 10,
                "wind_direction": "NE"
            })
        
        return {"weather": weather_data}
    
    def get_circuit_breaker_status(self) -> str:
        breaker = get_circuit_breaker("WeatherAPI")
        return breaker.state if breaker else "unknown"


weather_api_client = WeatherAPIClient()