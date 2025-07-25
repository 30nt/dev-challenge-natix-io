from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import uuid
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class RequestTrackerMiddleware(BaseHTTPMiddleware):
    """
    Middleware that tracks requests by adding:
    - Unique request ID for tracing
    - Processing time measurement
    - Structured logging of requests
    """
    
    async def dispatch(self, request: Request, call_next):
        request_id = f"req_{uuid.uuid4().hex[:8]}_{int(time.time() * 1000)}"
        request.state.request_id = request_id
        
        start_time = time.time()
        logger.debug(
            f"Incoming request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else "unknown"
            }
        )
        
        try:
            response = await call_next(request)
            
            process_time = time.time() - start_time
            
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            response.headers["X-Request-ID"] = request_id
            logger.debug(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "process_time": process_time
                }
            )
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {str(e)}",
                extra={
                    "request_id": request_id,
                    "process_time": process_time,
                    "error": str(e)
                }
            )
            
            return Response(
                content="Internal server error",
                status_code=500,
                headers={
                    "X-Process-Time": f"{process_time:.3f}",
                    "X-Request-ID": request_id
                }
            )