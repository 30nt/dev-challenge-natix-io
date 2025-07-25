from typing import Dict, Any

from pydantic import BaseModel, Field


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
    rate_limit_remaining: int = Field(..., description="Remaining API calls in current window")
    rate_limit_window_seconds: int = Field(..., description="Rate limit window duration")
    average_response_time_ms: float = Field(..., description="Average response time in milliseconds")
    error_rate: float = Field(..., description="Error rate percentage")
    circuit_breaker_status: str = Field(..., description="Circuit breaker status")
    top_cities: list[Dict[str, Any]] = Field(..., description="Most requested cities")
