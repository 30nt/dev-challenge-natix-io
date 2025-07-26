"""
Tests for the main application module.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestMainApplication:
    """Test suite for main FastAPI application configuration.

    Validates application setup, middleware configuration,
    router registration, and API documentation endpoints.
    """

    @pytest.fixture
    def client(self):
        """Create a FastAPI test client.

        Returns:
            TestClient: Configured test client for API testing
        """
        return TestClient(app)

    def test_app_creation(self):
        """Test FastAPI application initialization.

        Verifies that the application is created with correct
        metadata and documentation endpoints are properly configured
        for both Swagger UI and ReDoc interfaces.
        """
        assert app.title == "Weather Service API"
        assert app.version == "1.0.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
        assert app.openapi_url == "/openapi.json"

    def test_cors_middleware_added(self):
        """Test CORS middleware integration.

        Ensures Cross-Origin Resource Sharing middleware is
        properly configured to allow API access from web clients.
        """
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in str(middleware_classes)

    def test_request_id_middleware_added(self):
        """Test request ID middleware integration.

        Validates that request tracking middleware is installed
        for correlating logs and debugging distributed requests.
        """
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "RequestIDMiddleware" in str(middleware_classes)

    def test_routers_included(self):
        """Test API router registration.

        Verifies that all API version routers are properly
        mounted, including v1 (deprecated) and v2 endpoints
        for weather data, health checks, and metrics.
        """
        routes = [route.path for route in app.routes]

        assert any("/v1/weather" in route for route in routes)

        assert any("/v2/weather" in route for route in routes)
        assert any("/v2/health" in route for route in routes)
        assert any("/v2/metrics" in route for route in routes)

    def test_prometheus_metrics_endpoint(self):
        """Test Prometheus metrics endpoint availability.

        Ensures the application exposes metrics in Prometheus
        format for monitoring and alerting integration.
        """
        routes = [route.path for route in app.routes]
        assert any("/prometheus-metrics" in route for route in routes)
