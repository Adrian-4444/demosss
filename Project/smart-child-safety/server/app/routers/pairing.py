"""API Router for Secure Parent-Child Pairing Operations."""

from datetime import datetime, timedelta, timezone
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.child import ChildProfile, PairingCode, RegisteredDevice
from app.schemas.pairing import (
    DeviceSummary,
    PairingCodeClaimRequest,
    PairingCodeClaimResponse,
    PairingCodeCreateRequest,
    PairingCodeCreateResponse,
    PairingStatusResponse,
)
from app.security import (
    AuthenticatedPrincipal,
    generate_pairing_code,
    get_current_principal,
    hash_pairing_code,
    verify_guardian_child_access,
)
from app.services.rate_limiter import rate_limit_pairing_claim, rate_limit_pairing_create

logger = logging.getLogger("app.routers.pairing")
settings = get_settings()

router = APIRouter(prefix="/pairing", tags=["Pairing"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime object is timezone-aware in UTC (SQLite returns naive datetimes)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.post(
    "/create",
    response_model=PairingCodeCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Single-Use Pairing Code",
    description="Generate a short-lived single-use pairing invitation code for device onboarding.",
    dependencies=[Depends(rate_limit_pairing_create)],
)
def create_pairing_code(
    payload: PairingCodeCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    # Verify caller is an authorized guardian for this child
    child = verify_guardian_child_access(
        child_profile_id=payload.child_profile_id,
        principal=principal,
        db=db,
        allowed_roles=["owner", "guardian"],
    )

    # Invalidate previous unclaimed codes for this child
    db.query(PairingCode).filter(
        PairingCode.child_profile_id == child.id,
        PairingCode.is_claimed.is_(False),
    ).update({"expires_at": utc_now()})

    # Generate human-friendly random code and hash it
    raw_code = generate_pairing_code(length=6)
    code_hash = hash_pairing_code(raw_code)
    expires_at = utc_now() + timedelta(minutes=settings.pairing_code_expiry_minutes)

    pairing_entry = PairingCode(
        family_id=child.family_id,
        child_profile_id=child.id,
        created_by_user_id=principal.id,
        code_hash=code_hash,
        expires_at=expires_at,
        is_claimed=False,
        attempts_count=0,
    )
    db.add(pairing_entry)
    db.commit()

    logger.info(
        "Pairing code issued for child_id=%s by user_id=%s (expires_in=%dm)",
        child.id,
        principal.id,
        settings.pairing_code_expiry_minutes,
    )

    # Raw code returned only once here; never stored or logged
    return PairingCodeCreateResponse(
        pairing_code=raw_code,
        expires_at=expires_at,
        child_profile_id=child.id,
    )


@router.post(
    "/claim",
    response_model=PairingCodeClaimResponse,
    status_code=status.HTTP_200_OK,
    summary="Redeem Pairing Code (Child Device)",
    description="Redeem a pairing invitation code to register and bind a child Android device.",
    dependencies=[Depends(rate_limit_pairing_claim)],
)
def claim_pairing_code(
    payload: PairingCodeClaimRequest,
    db: Session = Depends(get_db),
):
    incoming_hash = hash_pairing_code(payload.pairing_code)

    pairing_entry = (
        db.query(PairingCode)
        .filter(PairingCode.code_hash == incoming_hash)
        .order_by(PairingCode.created_at.desc())
        .first()
    )

    if not pairing_entry:
        logger.warning("Pairing attempt with invalid code hash")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pairing code",
        )

    # Track attempts count
    pairing_entry.attempts_count += 1
    if pairing_entry.attempts_count > settings.pairing_max_attempts:
        db.commit()
        logger.warning("Pairing code attempts exceeded max limit for id=%s", pairing_entry.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pairing code has exceeded maximum verification attempts",
        )

    if pairing_entry.is_claimed:
        db.commit()
        logger.warning("Attempted to reuse already-claimed pairing code id=%s", pairing_entry.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pairing code has already been redeemed",
        )

    now = utc_now()
    if ensure_utc(pairing_entry.expires_at) < now:
        db.commit()
        logger.warning("Attempted to claim expired pairing code id=%s", pairing_entry.id)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Pairing code has expired",
        )

    # Register or update the physical Android device
    device = (
        db.query(RegisteredDevice)
        .filter(RegisteredDevice.device_identifier == payload.device_identifier.strip())
        .first()
    )

    if device:
        # Re-bind existing hardware to this child
        device.child_profile_id = pairing_entry.child_profile_id
        device.device_model = payload.device_model
        device.os_version = payload.os_version
        device.app_version = payload.app_version
        if payload.fcm_token:
            device.fcm_token = payload.fcm_token
        device.is_active = True
        device.last_seen_at = now
    else:
        device = RegisteredDevice(
            child_profile_id=pairing_entry.child_profile_id,
            device_identifier=payload.device_identifier.strip(),
            device_model=payload.device_model,
            os_version=payload.os_version,
            app_version=payload.app_version,
            fcm_token=payload.fcm_token,
            is_active=True,
            last_seen_at=now,
        )
        db.add(device)

    db.flush()  # Ensures device.id is populated

    # Mark code as consumed atomically
    pairing_entry.is_claimed = True
    pairing_entry.claimed_by_device_id = device.id
    pairing_entry.claimed_at = now

    db.commit()
    db.refresh(device)

    logger.info(
        "Successfully paired device_id=%s to child_id=%s",
        device.id,
        pairing_entry.child_profile_id,
    )

    return PairingCodeClaimResponse(
        status="paired",
        child_profile_id=pairing_entry.child_profile_id,
        family_id=pairing_entry.family_id,
        device_id=device.id,
        paired_at=now,
    )


@router.get(
    "/status/{child_id}",
    response_model=PairingStatusResponse,
    summary="Get Child Pairing Status",
    description="Retrieve list of active devices registered to a child profile.",
)
def get_pairing_status(
    child_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    child = verify_guardian_child_access(
        child_profile_id=child_id,
        principal=principal,
        db=db,
    )

    devices = (
        db.query(RegisteredDevice)
        .filter(
            RegisteredDevice.child_profile_id == child.id,
            RegisteredDevice.is_active.is_(True),
        )
        .all()
    )

    device_summaries = [DeviceSummary.model_validate(d) for d in devices]

    return PairingStatusResponse(
        child_profile_id=child.id,
        has_active_device=len(device_summaries) > 0,
        devices=device_summaries,
    )


@router.delete(
    "/revoke/{child_id}/devices/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke Device Association",
    description="Unpair and deactivate an authorized device from a child profile.",
)
def revoke_device_pairing(
    child_id: str,
    device_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    child = verify_guardian_child_access(
        child_profile_id=child_id,
        principal=principal,
        db=db,
        allowed_roles=["owner", "guardian"],
    )

    device = (
        db.query(RegisteredDevice)
        .filter(
            RegisteredDevice.id == device_id,
            RegisteredDevice.child_profile_id == child.id,
        )
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Registered device not found for this child profile",
        )

    device.is_active = False
    device.fcm_token = None
    device.updated_at = utc_now()
    db.commit()
    logger.info("Deactivated device id=%s (revoked tokens) for child id=%s by user=%s", device_id, child.id, principal.id)

