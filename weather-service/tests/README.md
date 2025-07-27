# Weather Service Tests

This directory contains all tests for the Weather Service API. The test structure mirrors the application structure for easy navigation and maintenance.

## Test Structure

```
tests/
├── api/                    # API endpoint tests
│   ├── v1/                # V1 API tests
│   │   └── test_routes.py
│   └── v2/                # V2 API tests
│       └── test_routes.py
├── services/              # Service layer tests
│   ├── test_rate_limit_service.py
│   └── test_weather_cache_service.py
├── utils/                 # Utility tests
│   ├── test_circuit_breaker.py
│   └── test_logger.py
├── conftest.py           # Common test fixtures
├── test_config.py        # Configuration tests
└── test_main.py          # Main application tests
```

## Running Tests

Run all tests:
```bash
poetry run pytest tests/
```

Run tests with coverage:
```bash
poetry run pytest tests/ --cov=app --cov-report=html
```

Run specific test file:
```bash
poetry run pytest tests/services/test_rate_limit_service.py
```

Run tests with verbose output:
```bash
poetry run pytest tests/ -v
```

## Writing Tests

1. Place test files in the appropriate subdirectory matching the app structure
2. Name test files with `test_` prefix followed by the module name
3. Use descriptive test method names that explain what is being tested
4. Mock external dependencies (Redis, external APIs, etc.)
5. Use fixtures from `conftest.py` for common setup

## Test Conventions

- All test classes should be named `Test<ModuleName>`
- Test methods should start with `test_`
- Use `@pytest.mark.asyncio` for async test methods
- Mock external dependencies to ensure tests run without external services
- Keep tests focused and test one thing at a time