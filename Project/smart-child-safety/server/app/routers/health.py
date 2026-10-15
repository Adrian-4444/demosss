"""Health and readiness endpoints for monitoring and orchestrator health checks."""

from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app import __version__
from app.config import get_settings
from app.database import check_db_connection

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get(
    "/health",
    summary="Service Liveness Check",
    description="Returns basic application liveness status without exposing internal configurations or secrets.",
    status_code=status.HTTP_200_OK,
)
def get_health() -> Dict[str, Any]:
    """Basic liveness probe."""
    return {
        "status": "ok",
        "service": settings.project_name,
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/ready",
    summary="Service Readiness Check",
    description="Verifies that backing dependencies (database) are reachable and ready to serve traffic.",
)
def get_readiness():
    """Readiness probe that checks backing services without leaking credentials."""
    db_ok = check_db_connection()
    timestamp = datetime.now(timezone.utc).isoformat()

    if not db_ok:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "timestamp": timestamp,
            },
        )

    return {
        "status": "ready",
        "database": "connected",
        "timestamp": timestamp,
    }
