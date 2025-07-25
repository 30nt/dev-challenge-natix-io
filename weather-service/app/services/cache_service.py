import redis.asyncio as redis
from typing import Optional, Dict, Any, List
import json
from datetime import datetime, timedelta, UTC
from app.config import get_settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class CacheService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    async def initialize(self):
        try:
            self.redis_client = redis.from_url(
                settings.redis_url, decode_responses=settings.redis_decode_responses
            )
            await self.redis_client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def close(self):
        if self.redis_client:
            await self.redis_client.close()

    def _get_weather_key(self, city: str, date: str) -> str:
        return f"weather:{city.lower()}:{date}"

    def _get_meta_key(self, city: str) -> str:
        return f"weather:meta:{city.lower()}:last_update"

    def _get_stats_key(self, city: str) -> str:
        return f"weather:stats:{city.lower()}:request_count"

    async def get_weather(self, city: str, date: str) -> Optional[Dict[str, Any]]:
        try:
            key = self._get_weather_key(city, date)
            data = await self.redis_client.get(key)

            if data:
                await self._increment_stats(city)
                return json.loads(data)

            return None
        except Exception as e:
            logger.error(f"Error getting weather from cache: {e}")
            return None

    async def set_weather(
        self,
        city: str,
        date: str,
        weather_data: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ):
        try:
            key = self._get_weather_key(city, date)
            ttl = ttl_seconds or settings.redis_cache_ttl

            await self.redis_client.setex(key, ttl, json.dumps(weather_data))

            meta_key = self._get_meta_key(city)
            await self.redis_client.setex(
                meta_key, settings.redis_stale_ttl, datetime.now(UTC).isoformat()
            )

            logger.info(f"Cached weather data for {city} with TTL {ttl}s")
        except Exception as e:
            logger.error(f"Error setting weather in cache: {e}")

    async def get_stale_weather(self, city: str, date: str) -> Optional[Dict[str, Any]]:
        try:
            key = self._get_weather_key(city, date)

            stale_key = f"{key}:stale"
            data = await self.redis_client.get(stale_key)

            if data:
                return json.loads(data)

            data = await self.redis_client.get(key)
            if data:
                await self.redis_client.setex(stale_key, settings.redis_stale_ttl, data)
                return json.loads(data)

            return None
        except Exception as e:
            logger.error(f"Error getting stale weather from cache: {e}")
            return None

    async def _increment_stats(self, city: str):
        try:
            stats_key = self._get_stats_key(city)
            await self.redis_client.incr(stats_key)
            await self.redis_client.expire(stats_key, 86400 * 7)
        except Exception as e:
            logger.error(f"Error incrementing stats: {e}")

    async def get_top_cities(self, count: int = 50) -> List[tuple[str, int]]:
        try:
            pattern = "weather:stats:*:request_count"
            cursor = 0
            city_stats = []

            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor, match=pattern, count=100
                )

                for key in keys:
                    city = key.split(":")[2]
                    count_str = await self.redis_client.get(key)
                    if count_str:
                        city_stats.append((city, int(count_str)))

                if cursor == 0:
                    break

            city_stats.sort(key=lambda x: x[1], reverse=True)
            return city_stats[:count]

        except Exception as e:
            logger.error(f"Error getting top cities: {e}")
            return []

    async def get_rate_limit_remaining(self) -> int:
        try:
            key = "rate_limit:tokens"
            tokens = await self.redis_client.get(key)
            return int(tokens) if tokens else settings.rate_limit_requests
        except Exception as e:
            logger.error(f"Error getting rate limit: {e}")
            return 0

    async def consume_rate_limit_token(self) -> bool:
        try:
            key = "rate_limit:tokens"
            window_key = "rate_limit:window_start"

            current_time = datetime.now(UTC)
            window_start = await self.redis_client.get(window_key)

            if not window_start:
                await self.redis_client.setex(
                    window_key, settings.rate_limit_window, current_time.isoformat()
                )
                await self.redis_client.setex(
                    key, settings.rate_limit_window, settings.rate_limit_requests - 1
                )
                return True

            window_start_time = datetime.fromisoformat(window_start)
            if current_time - window_start_time > timedelta(
                seconds=settings.rate_limit_window
            ):
                await self.redis_client.setex(
                    window_key, settings.rate_limit_window, current_time.isoformat()
                )
                await self.redis_client.setex(
                    key, settings.rate_limit_window, settings.rate_limit_requests - 1
                )
                return True

            tokens = await self.redis_client.get(key)
            if tokens and int(tokens) > 0:
                await self.redis_client.decr(key)
                return True

            return False

        except Exception as e:
            logger.error(f"Error consuming rate limit token: {e}")
            return False

    async def add_to_queue(self, city: str, priority: int = 0):
        try:
            queue_key = "weather:queue:cities"
            score = -priority
            await self.redis_client.zadd(queue_key, {city: score})
            logger.info(f"Added {city} to queue with priority {priority}")
        except Exception as e:
            logger.error(f"Error adding to queue: {e}")

    async def get_from_queue(self) -> Optional[str]:
        try:
            queue_key = "weather:queue:cities"
            result = await self.redis_client.zpopmin(queue_key)
            if result:
                return result[0][0]
            return None
        except Exception as e:
            logger.error(f"Error getting from queue: {e}")
            return None
