# Resilient Weather Service

A resilient backend API that efficiently serves weather data while minimizing calls to external weather APIs and handling failures gracefully. Built to support ~100,000 daily active users across ~2,500 cities with a rate limit of 100 external API requests per hour.

**🔍 This is a demonstration application that uses realistic mock weather data instead of connecting to real external weather APIs.**

## Challenge Solution

This project addresses the challenge requirements:

### Core Requirements Met
- **Moderates External API Calls**: Intelligent caching with Redis and proactive cache warming for top cities
- **Handles API Failures Gracefully**: Circuit breaker pattern, exponential backoff retries, and fallback to stale data
- **Rate Limit Compliance**: Built-in rate limiting to stay within 100 requests/hour
- **Scale Support**: Designed to handle 100,000 daily users across 2,500 cities

### Key Features
- **Multi-tier Caching**: Fresh cache (1h TTL) + stale cache (24h TTL) for resilience
- **Intelligent Cache Warming**: Background service preloads weather data for popular cities
- **Circuit Breaker**: Prevents cascading failures when external API is down
- **Request Queue**: Priority-based queue for handling failed requests
- **Dual API Versions**: v1 (challenge format) and v2 (enhanced with metadata)
- **Comprehensive Monitoring**: Health checks, metrics, and request tracking

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │───▶│   Weather API    │───▶│  External API   │
│                 │    │   (FastAPI)      │    │  (Rate Limited) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │      Redis       │
                       │   - Fresh Cache  │
                       │   - Stale Cache  │
                       │   - Rate Limits  │
                       └──────────────────┘
                              ▲
                              │
                       ┌──────────────────┐
                       │  Cache Warmer    │
                       │ (Background Job) │
                       └──────────────────┘
```

### Components
- **FastAPI**: Async web framework for high performance
- **Redis**: Multi-purpose storage for caching, rate limiting, and queue management
- **Circuit Breaker**: Protects against external API failures
- **Cache Warming Service**: Proactively refreshes popular city data
- **Request Queue**: Handles retries for failed external API calls

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Start all services (Redis + Weather API)
docker-compose up

# API will be available at http://localhost:8000
# Redis dashboard at http://localhost:6379
```

### Manual Setup

1. **Prerequisites**:
   - Python 3.11+
   - Redis server
   - Poetry package manager

2. **Installation**:
   ```bash
   # Install Poetry
   curl -sSL https://install.python-poetry.org | python3 -
   
   # Install dependencies
   poetry install
   
   # Configure environment
   cp .env.example .env
   # Edit .env with your Redis URL and other settings
   ```

3. **Run Services**:
   ```bash
   # Start Redis (in separate terminal)
   redis-server
   
   # Start Weather API
   poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Endpoints

### API Versions

The Weather Service API supports two versions:

#### Version 1 (Challenge Format)
Matches the exact format specified in the challenge requirements.

```
GET /v1/weather?city=London
```

Response:
```json
{
  "weather": [
    { "hour": 0, "temperature": "18", "condition": "Clear" },
    { "hour": 1, "temperature": "17", "condition": "Clear" },
    { "hour": 2, "temperature": "16", "condition": "Clear" },
    { "hour": 23, "temperature": "16", "condition": "Cloudy" }
  ]
}
```

#### Version 2 (Enhanced)
Improved response format with metadata, additional weather attributes, and data freshness indicators.

```
GET /v2/weather?city=London
GET /weather?city=London  (same as v2, without prefix)
```

Response:
```json
{
  "city": "London",
  "date": "2025-07-26",
  "weather": [
    {
      "hour": 0,
      "temperature": "18",
      "temperature_unit": "celsius",
      "condition": "Clear",
      "feels_like": 16,
      "humidity": 65,
      "wind_speed": 10,
      "wind_direction": "NE"
    }
  ],
  "metadata": {
    "request_id": "req_12345",
    "last_updated": "2025-07-26T10:30:00Z",
    "data_freshness": "fresh",
    "source": "cache",
    "cache_hit": true
  },
  "warnings": []
}
```

**Data Freshness Indicators**:
- `fresh`: Data is within cache TTL (< 1 hour)
- `stale`: Data is older but still acceptable (< 24 hours)
- `unavailable`: No data available, request has been queued

**Source Indicators**:
- `cache`: Data retrieved from Redis cache
- `api`: Data retrieved from external API
- `unavailable`: No data source available

### Monitoring Endpoints

```bash
# Health check
GET /health

# Application metrics and statistics
GET /metrics

# Prometheus metrics (for monitoring)
GET /prometheus
```

## Configuration

Key configuration options in `.env`:

```bash
# External API Rate Limiting
RATE_LIMIT_REQUESTS=100              # Max external API calls per hour
RATE_LIMIT_WINDOW=3600               # Rate limit window in seconds

# Caching Strategy
REDIS_CACHE_TTL=3600                 # Fresh cache TTL (1 hour)
REDIS_STALE_TTL=86400               # Stale cache TTL (24 hours)

# Cache Warming
ENABLE_CACHE_WARMING=true           # Enable proactive caching
CACHE_WARM_INTERVAL=3600            # Cache warming interval
TOP_CITIES_COUNT=10                 # Number of cities to pre-cache
CACHE_WARM_MAX_TOKENS=20            # Max rate limit tokens for warming

# Resilience
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5  # Failures before circuit opens
RETRY_MAX_ATTEMPTS=3                # Max retry attempts
```

See `.env.example` for complete configuration options.

## Testing & Development

### Running Tests
```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test categories
poetry run pytest tests/services/        # Service tests
poetry run pytest tests/api/             # API tests
poetry run pytest tests/background/      # Background job tests
```

### Code Quality
```bash
# Format code
poetry run black app/

# Lint code
poetry run pylint app/
```

### Example API Calls
```bash
# Test the API
curl "http://localhost:8000/v1/weather?city=London"
curl "http://localhost:8000/v2/weather?city=Paris"
curl "http://localhost:8000/health"
curl "http://localhost:8000/metrics"
```

## Technical Implementation

### Key Design Decisions

1. **Multi-tier Caching Strategy**:
   - Fresh cache (1h TTL) for optimal user experience
   - Stale cache (24h TTL) as fallback during API outages
   - Intelligent cache warming for top cities

2. **Rate Limit Management**:
   - Token bucket algorithm with Redis
   - Reserve tokens for cache warming vs user requests
   - Graceful degradation when tokens exhausted

3. **Resilience Patterns**:
   - Circuit breaker to prevent cascading failures
   - Exponential backoff retries with jitter
   - Queue system for handling failed requests

4. **Performance Optimizations**:
   - Async/await throughout for high concurrency
   - Connection pooling for Redis and HTTP clients
   - Background task scheduling for cache warming

### Dependencies
- **FastAPI**: Modern async web framework
- **Redis**: High-performance caching and rate limiting
- **Pydantic**: Data validation and settings management
- **Tenacity**: Robust retry logic with backoff
- **HTTPX**: Async HTTP client for external API calls

## Challenge Compliance

✅ **Rate Limit Compliance**: Respects 100 requests/hour limit
✅ **Scalability**: Supports 100k users across 2.5k cities
✅ **Resilience**: Graceful handling of API failures
✅ **Efficiency**: Minimizes external API calls through intelligent caching
✅ **Response Format**: Supports original challenge format (v1) + enhanced format (v2)