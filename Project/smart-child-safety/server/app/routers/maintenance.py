"""API router for Maintenance and Data Retention Lifecycle Management."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import RetentionCleanupResponse
from app.security import AuthenticatedPrincipal, get_current_principal
from app.services.retention import run_retention_cleanup

logger = logging.getLogger("app.routers.maintenance")

router = APIRouter(prefix="/maintenance", tags=["Maintenance & Data Retention"])


@router.post(
    "/retention/cleanup",
    response_model=RetentionCleanupResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Data Retention Cleanup",
    description=(
        "Purges historical location records and telemetry heartbeats exceeding retention limits, "
        "and removes expired unredeemed pairing codes. Atomic and privacy-preserving."
    ),
)
def trigger_retention_cleanup(
    retention_days: Optional[int] = Query(
        None,
        ge=1,
        le=365,
        description="Override retention window in days (defaults to system configuration)",
    ),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Trigger data retention prune job."""
    # Ensure caller is active
    if not principal.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated or disabled",
        )

    logger.info("Retention cleanup triggered by principal id=%s (role=%s)", principal.id, principal.role)
    metrics = run_retention_cleanup(db=db, location_retention_days=retention_days)
    return metrics
