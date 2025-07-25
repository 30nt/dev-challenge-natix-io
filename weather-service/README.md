# Weather Service API

A resilient weather service API built with FastAPI and Redis that efficiently serves weather data while respecting external API rate limits.

## Features

- **Efficient Caching**: Redis-based caching with TTL management
- **Rate Limiting**: Stays within 100 requests/hour limit to external API
- **Resilience**: Circuit breaker, retry logic, and fallback to stale data
- **Cache Warming**: Proactive caching for popular cities
- **Request Tracking**: Unique request IDs and performance monitoring
- **Monitoring**: Health checks and metrics endpoints
- **Queue System**: Priority-based queue for failed requests

## Architecture

- **FastAPI**: Modern async web framework
- **Redis**: Caching and rate limiting
- **Circuit Breaker**: Prevents cascading failures
- **Background Tasks**: Cache warming for popular cities

## Quick Start

### Using Docker Compose

```bash
docker-compose up
```

### Manual Setup

1. Install Python 3.12+
2. Install Poetry:
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
3. Install Redis
4. Install dependencies:
   ```bash
   poetry install
   ```
5. Copy `.env.example` to `.env` and configure
6. Run the application:
   ```bash
   poetry run uvicorn app.main:app --reload
   ```

## API Endpoints

### Get Weather
```
GET /weather?city=London
```

Response:
```json
{
  "city": "London",
  "date": "2024-01-15",
  "weather": [
    {
      "hour": 0,
      "temperature": 18,
      "temperature_unit": "celsius",
      "condition": "Clear",
      "feels_like": 16,
      "humidity": 65,
      "wind_speed": 10,
      "wind_direction": "NE"
    }
  ],
  "metadata": {
    "last_updated": "2024-01-15T10:30:00Z",
    "data_freshness": "fresh",
    "cache_ttl_seconds": 3600,
    "source": "cache"
  },
  "warnings": []
}
```

### Health Check
```
GET /health
```

### Metrics
```
GET /metrics
```

## Configuration

See `.env.example` for all configuration options.

Key settings:
- `RATE_LIMIT_REQUESTS`: Max requests per hour (default: 100)
- `REDIS_CACHE_TTL`: Cache duration in seconds (default: 3600)
- `ENABLE_CACHE_WARMING`: Enable proactive caching (default: true)

## Development Tools

### Code Formatting
```bash
poetry run black app/
poetry run isort app/
```

### Linting
```bash
poetry run pylint app/
poetry run mypy app/
```

### Testing
```bash
poetry run pytest
poetry run pytest --cov=app --cov-report=html
```

## Development

The service uses:
- Async/await for better performance
- Pydantic for data validation
- Structured logging
- Circuit breaker pattern
- Exponential backoff retries