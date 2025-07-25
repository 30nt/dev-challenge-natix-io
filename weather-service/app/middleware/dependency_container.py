from app.services.weather_service import WeatherService, WeatherServiceV2
from app.services.cache_service import CacheService


class DependencyContainer:
    def __init__(self):
        self.cache_service = None
        self.weather_service = None
        self.weather_service_v2 = None

    def set_cache_service(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.weather_service = WeatherService(cache_service)
        self.weather_service_v2 = WeatherServiceV2(cache_service)


container = DependencyContainer()
