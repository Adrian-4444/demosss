"""FastAPI application entry point for the Smart Child Monitoring and Safety System."""

import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.routers import (
    command_router,
    family_router,
    health_router,
    location_router,
    maintenance_router,
    pairing_router,
    safety_router,
    user_router,
    websocket_router,
)



# ------------------------------------------------------------------------------
# Logging Setup
# ------------------------------------------------------------------------------
settings = get_settings()

log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("app.main")


# ------------------------------------------------------------------------------
# Application Lifespan
# ------------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for clean startup and shutdown."""
    logger.info("Starting %s (v%s) in '%s' environment", settings.project_name, __version__, settings.environment)
    logger.info("API prefix mounted at: %s", settings.api_v1_prefix)
    yield
    logger.info("Shutting down %s", settings.project_name)


# ------------------------------------------------------------------------------
# FastAPI Application Creation
# ------------------------------------------------------------------------------
app = FastAPI(
    title=settings.project_name,
    description=(
        "Backend API for the Smart Child Monitoring and Safety System. "
        "Provides context-aware geofencing, remote device enforcement, "
        "durable command dispatch, and authenticated real-time updates."
    ),
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan,
)

# ------------------------------------------------------------------------------
# Middlewares
# ------------------------------------------------------------------------------

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if isinstance(settings.cors_origins, list) else [settings.cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# 2. Privacy-Safe Request Tracking & Structured Access Logging Middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Attach unique request ID and record privacy-safe access metrics.
    
    Never logs authorization tokens, passwords, raw location coordinates or sensitive payloads.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id

        # Redact query params in log if needed, log route and status
        logger.info(
            "request_id=%s method=%s path=%s status=%d duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            "request_id=%s method=%s path=%s status=500 duration_ms=%.2f error=%s",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )


# ------------------------------------------------------------------------------
# Routers Registration
# ------------------------------------------------------------------------------
# Root-level health & readiness for container/Render orchestrators
app.include_router(health_router)

# Versioned routes under /api/v1
app.include_router(health_router, prefix=settings.api_v1_prefix)
app.include_router(user_router, prefix=settings.api_v1_prefix)
app.include_router(family_router, prefix=settings.api_v1_prefix)
app.include_router(pairing_router, prefix=settings.api_v1_prefix)
app.include_router(location_router, prefix=settings.api_v1_prefix)
app.include_router(command_router, prefix=settings.api_v1_prefix)
app.include_router(safety_router, prefix=settings.api_v1_prefix)
app.include_router(maintenance_router, prefix=settings.api_v1_prefix)
app.include_router(websocket_router, prefix=settings.api_v1_prefix)



if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
