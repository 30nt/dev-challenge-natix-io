"""
This module is the entry point for the application.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import routes as v1_routes
from app.api.v2 import routes as v2_routes
from app.background.cache_warmer import start_cache_warmer
from app.config import get_settings
from app.middleware.dependency_container import container
from app.middleware.request_id import RequestIDMiddleware
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    This function manages the application's lifespan.
    """
    logger.info("Starting Weather Service API...")

    await container.initialize()

    if settings.enable_cache_warming:
        fastapi_app.state.cache_warmer_task = await start_cache_warmer(fastapi_app)

    yield

    logger.info("Shutting down Weather Service API...")

    if hasattr(fastapi_app.state, "cache_warmer_task"):
        fastapi_app.state.cache_warmer_task.cancel()

    await container.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

app.add_middleware(RequestIDMiddleware)

Instrumentator().instrument(app).expose(app, endpoint="/prometheus-metrics")

# Include API version routers
app.include_router(v1_routes.router)
app.include_router(v2_routes.router)

# Include default router (v2) without prefix for backward compatibility
app.include_router(v2_routes.router, prefix="", include_in_schema=False)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )
