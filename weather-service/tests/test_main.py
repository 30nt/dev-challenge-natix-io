"""
Tests for the main application module.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestMainApplication:
    """Test cases for the main FastAPI application."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    def test_app_creation(self):
        """Test that the app is created properly."""
        assert app.title == "Weather Service API"
        assert app.version == "1.0.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
        assert app.openapi_url == "/openapi.json"

    def test_cors_middleware_added(self):
        """Test that CORS middleware is added."""
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in str(middleware_classes)

    def test_request_id_middleware_added(self):
        """Test that RequestID middleware is added."""
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "RequestIDMiddleware" in str(middleware_classes)

    def test_routers_included(self):
        """Test that API routers are included."""
        routes = [route.path for route in app.routes]

        # Check v1 routes
        assert any("/v1/weather" in route for route in routes)

        # Check v2 routes
        assert any("/v2/weather" in route for route in routes)
        assert any("/v2/health" in route for route in routes)
        assert any("/v2/metrics" in route for route in routes)

    def test_prometheus_metrics_endpoint(self):
        """Test that Prometheus metrics endpoint is exposed."""
        routes = [route.path for route in app.routes]
        assert any("/prometheus-metrics" in route for route in routes)
