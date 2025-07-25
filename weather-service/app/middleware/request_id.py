"""
This module provides request ID tracking for the application.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Lightweight middleware that adds unique request IDs for tracing.

    This middleware focuses solely on request identification without
    duplicating monitoring functionality provided by Prometheus.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Add unique request ID to request state and response headers.
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}_{int(time.time() * 1000)}"
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
