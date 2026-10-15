"""API router for Location Ingestion, Live Tracking, History, and Device Telemetry."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.child import ChildProfile, RegisteredDevice
from app.models.command import DeviceHeartbeat
from app.models.location import LatestLocation, LocationRecord
from app.models.user import ensure_utc, utc_now
from app.schemas.location import (
    ChildDeviceStatusResponse,
    DeviceStatusUploadRequest,
    DeviceStatusUploadResponse,
    DeviceTelemetrySummary,
    LatestLocationResponse,
    LocationHistoryResponse,
    LocationIngestResponse,
    LocationPointResponse,
    LocationUploadRequest,
)
from app.security import (
    AuthenticatedPrincipal,
    CallerIdentity,
    get_current_principal,
    optional_bearer_scheme,
    verify_child_ingestion_auth,
    verify_guardian_child_access,
)
from app.services import geofence
from app.services.rate_limiter import rate_limit_location_upload
from app.websocket.manager import ws_manager

logger = logging.getLogger("app.routers.location")
settings = get_settings()

router = APIRouter(prefix="/children", tags=["Location & Device Status"])


def calculate_freshness(captured_at: datetime, now: datetime) -> str:
    """Calculate freshness state based on capture age and configuration."""
    age_seconds = (now - ensure_utc(captured_at)).total_seconds()
    if age_seconds <= 60:
        return "LIVE"
    elif age_seconds <= settings.location_stale_minutes * 60:
        return "FRESH"
    return "STALE"


@router.post(
    "/{child_id}/locations",
    response_model=LocationIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest Child Location Point",
    description=(
        "Ingest GPS position reported by an authenticated child device or guardian. "
        "Validates coordinates, clock drift, and data retention boundaries; updates the "
        "1:1 LatestLocation snapshot and appends to the immutable LocationRecord history."
    ),
    dependencies=[Depends(rate_limit_location_upload)],
)
async def ingest_child_location(
    child_id: str,
    payload: LocationUploadRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
):

    # 1. Authorize caller (Device hardware identifier or Guardian principal)
    caller: CallerIdentity = verify_child_ingestion_auth(
        child_id=child_id,
        request=request,
        db=db,
        credentials=credentials,
    )

    child = db.query(ChildProfile).filter(ChildProfile.id == child_id).first()
    if not child or child.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child profile not found",
        )

    # 2. Check sharing configuration
    if not child.sharing_enabled:
        logger.info("Location upload blocked: sharing disabled for child_id=%s", child_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Location sharing is currently disabled for this child profile",
        )

    now = utc_now()
    captured_utc = ensure_utc(payload.captured_at)

    # 3. Validate capture timestamp against future clock drift (> 5 minutes)
    if captured_utc > now + timedelta(minutes=5):
        logger.warning(
            "Rejected future-dated location: captured_at=%s, server_now=%s",
            captured_utc,
            now,
        )
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail="Location capture timestamp cannot be in the future (exceeds allowable 5-minute clock drift)",
        )

    # 4. Validate capture timestamp against retention window
    retention_cutoff = now - timedelta(days=settings.location_retention_days)
    if captured_utc < retention_cutoff:
        logger.warning(
            "Rejected location older than retention limit: captured_at=%s, retention_cutoff=%s",
            captured_utc,
            retention_cutoff,
        )
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=f"Location capture timestamp is older than the {settings.location_retention_days}-day data retention limit",
        )

    # 5. S-045 Duplicate Detection: exact child + captured_at match
    existing_record = (
        db.query(LocationRecord)
        .filter(
            LocationRecord.child_profile_id == child_id,
            LocationRecord.captured_at == captured_utc,
        )
        .first()
    )
    if existing_record:
        # Idempotent response for retransmitted duplicates
        freshness = calculate_freshness(captured_utc, now)
        logger.info(
            "Duplicate location detected for child_id=%s at %s; returning existing record_id=%s",
            child_id,
            captured_utc,
            existing_record.id,
        )
        return LocationIngestResponse(
            status="duplicate",
            record_id=existing_record.id,
            child_profile_id=child_id,
            device_id=existing_record.device_id,
            captured_at=existing_record.captured_at,
            received_at=existing_record.received_at,
            freshness_status=freshness,
            is_latest=False,
        )

    freshness = calculate_freshness(captured_utc, now)

    # 6. Append immutable time-series record
    record = LocationRecord(
        child_profile_id=child_id,
        device_id=caller.device_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
        speed_mps=payload.speed_mps,
        bearing_deg=payload.bearing_deg,
        altitude_m=payload.altitude_m,
        captured_at=captured_utc,
        received_at=now,
    )
    db.add(record)

    # 7. S-045 Out-of-Order Handling: only advance LatestLocation if point is newer
    latest = (
        db.query(LatestLocation)
        .filter(LatestLocation.child_profile_id == child_id)
        .first()
    )

    is_latest = True
    if latest:
        if captured_utc >= ensure_utc(latest.captured_at):
            latest.device_id = caller.device_id
            latest.latitude = payload.latitude
            latest.longitude = payload.longitude
            latest.accuracy_m = payload.accuracy_m
            latest.speed_mps = payload.speed_mps
            latest.bearing_deg = payload.bearing_deg
            latest.altitude_m = payload.altitude_m
            latest.captured_at = captured_utc
            latest.received_at = now
            latest.freshness_status = freshness
            is_latest = True
        else:
            # Out-of-order point: preserved in history, but latest location does not regress
            is_latest = False
            logger.info(
                "Out-of-order location for child_id=%s: captured_at=%s older than latest=%s",
                child_id,
                captured_utc,
                latest.captured_at,
            )
    else:
        latest = LatestLocation(
            child_profile_id=child_id,
            device_id=caller.device_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy_m=payload.accuracy_m,
            speed_mps=payload.speed_mps,
            bearing_deg=payload.bearing_deg,
            altitude_m=payload.altitude_m,
            captured_at=captured_utc,
            received_at=now,
            freshness_status=freshness,
        )
        db.add(latest)
        is_latest = True

    # 8. Update device last seen timestamp if device is known
    if caller.device_id:
        device = (
            db.query(RegisteredDevice)
            .filter(RegisteredDevice.id == caller.device_id)
            .first()
        )
        if device:
            device.last_seen_at = now

    db.commit()
    db.refresh(record)

    # 9. S-062 Geofence Evaluation & Safe Zone Transition Detection
    try:
        events = geofence.evaluate_safe_zones_for_location(
            child_id=child_id,
            family_id=child.family_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            captured_at=captured_utc,
            db=db,
            is_latest=is_latest,
        )
        for ev in events:
            await ws_manager.broadcast_to_child(
                child_id=child_id,
                message={
                    "event": "zone_transition",
                    "child_id": child_id,
                    "event_id": ev.id,
                    "zone_id": ev.zone_id,
                    "event_type": ev.event_type,
                    "severity": ev.severity,
                    "reason": ev.reason,
                    "created_at": ev.created_at.isoformat(),
                },
            )
    except Exception as exc:
        logger.error("Error evaluating safe zones for child_id=%s: %s", child_id, exc)

    # 10. Real-time Location Broadcast to connected WebSocket subscribers
    try:
        await ws_manager.broadcast_to_child(
            child_id=child_id,
            message={
                "event": "location_update",
                "child_id": child_id,
                "record_id": record.id,
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "accuracy_m": payload.accuracy_m,
                "captured_at": record.captured_at.isoformat(),
                "freshness_status": freshness,
                "is_latest": is_latest,
            },
        )
    except Exception as exc:
        logger.debug("WebSocket location broadcast skipped or error: %s", exc)

    return LocationIngestResponse(
        status="success",
        record_id=record.id,
        child_profile_id=child_id,
        device_id=caller.device_id,
        captured_at=record.captured_at,
        received_at=record.received_at,
        freshness_status=freshness,
        is_latest=is_latest,
    )



@router.get(
    "/{child_id}/location/latest",
    response_model=LatestLocationResponse,
    summary="Get Child Latest Location",
    description=(
        "Retrieve the newest valid GPS location for an authorized child. "
        "Dynamically derives freshness status (LIVE, FRESH, STALE, NOT_REPORTING)."
    ),
)
def get_child_latest_location(
    child_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    # Verify guardian has access to this child
    child = verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)
    now = utc_now()

    if not child.sharing_enabled:
        return LatestLocationResponse(
            child_profile_id=child_id,
            freshness_status="NOT_REPORTING",
            sharing_enabled=False,
            location=None,
            retrieved_at=now,
        )

    latest = (
        db.query(LatestLocation)
        .filter(LatestLocation.child_profile_id == child_id)
        .first()
    )

    if not latest:
        return LatestLocationResponse(
            child_profile_id=child_id,
            freshness_status="NOT_REPORTING",
            sharing_enabled=True,
            location=None,
            retrieved_at=now,
        )

    # Dynamic freshness calculation
    age_seconds = max(0.0, (now - ensure_utc(latest.captured_at)).total_seconds())
    freshness = calculate_freshness(latest.captured_at, now)

    location_point = LocationPointResponse(
        id=latest.id,
        child_profile_id=child_id,
        device_id=latest.device_id,
        latitude=latest.latitude,
        longitude=latest.longitude,
        accuracy_m=latest.accuracy_m,
        speed_mps=latest.speed_mps,
        bearing_deg=latest.bearing_deg,
        altitude_m=latest.altitude_m,
        captured_at=latest.captured_at,
        received_at=latest.received_at,
        freshness_status=freshness,
        age_seconds=round(age_seconds, 1),
    )

    return LatestLocationResponse(
        child_profile_id=child_id,
        freshness_status=freshness,
        sharing_enabled=True,
        location=location_point,
        retrieved_at=now,
    )


@router.get(
    "/{child_id}/locations",
    response_model=LocationHistoryResponse,
    summary="Get Paginated Location History",
    description=(
        "Retrieve historical GPS trajectory points for an authorized child. "
        "Enforces strict data retention boundaries and chronological descending pagination."
    ),
)
def get_child_location_history(
    child_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Items offset"),
    start_time: Optional[datetime] = Query(default=None, description="Start timestamp (UTC)"),
    end_time: Optional[datetime] = Query(default=None, description="End timestamp (UTC)"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    # Verify guardian has access to this child
    verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)

    now = utc_now()
    retention_cutoff = now - timedelta(days=settings.location_retention_days)

    # Bounded start_time: cannot query older than retention policy
    if start_time:
        effective_start = max(ensure_utc(start_time), retention_cutoff)
    else:
        effective_start = retention_cutoff

    query = db.query(LocationRecord).filter(
        LocationRecord.child_profile_id == child_id,
        LocationRecord.captured_at >= effective_start,
    )

    if end_time:
        query = query.filter(LocationRecord.captured_at <= ensure_utc(end_time))

    total = query.count()
    records = (
        query.order_by(LocationRecord.captured_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [
        LocationPointResponse(
            id=rec.id,
            child_profile_id=rec.child_profile_id,
            device_id=rec.device_id,
            latitude=rec.latitude,
            longitude=rec.longitude,
            accuracy_m=rec.accuracy_m,
            speed_mps=rec.speed_mps,
            bearing_deg=rec.bearing_deg,
            altitude_m=rec.altitude_m,
            captured_at=rec.captured_at,
            received_at=rec.received_at,
            freshness_status=None,
            age_seconds=round(max(0.0, (now - ensure_utc(rec.captured_at)).total_seconds()), 1),
        )
        for rec in records
    ]

    return LocationHistoryResponse(
        child_profile_id=child_id,
        total=total,
        limit=limit,
        offset=offset,
        retention_days=settings.location_retention_days,
        retention_cutoff=retention_cutoff,
        items=items,
    )


@router.post(
    "/{child_id}/status",
    response_model=DeviceStatusUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Device Telemetry / Heartbeat",
    description="Record hardware health telemetry (battery, charging, network, permissions) for a child device.",
    dependencies=[Depends(rate_limit_location_upload)],
)
def upload_device_status(
    child_id: str,
    payload: DeviceStatusUploadRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
):
    caller: CallerIdentity = verify_child_ingestion_auth(
        child_id=child_id,
        request=request,
        db=db,
        credentials=credentials,
    )

    child = db.query(ChildProfile).filter(ChildProfile.id == child_id).first()
    if not child or child.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Child profile not found",
        )

    now = utc_now()
    target_device_id = caller.device_id

    # If caller did not provide device_id, fall back to child's primary registered device if exists
    if not target_device_id:
        dev = (
            db.query(RegisteredDevice)
            .filter(
                RegisteredDevice.child_profile_id == child_id,
                RegisteredDevice.is_active == True,
            )
            .first()
        )
        if dev:
            target_device_id = dev.id

    # If target device exists, update its state
    if target_device_id:
        device = db.query(RegisteredDevice).filter(RegisteredDevice.id == target_device_id).first()
        if device:
            if payload.battery_percent is not None:
                device.battery_percent = payload.battery_percent
            if payload.is_charging is not None:
                device.is_charging = payload.is_charging
            if payload.location_permission_state:
                device.location_permission_state = payload.location_permission_state
            device.last_seen_at = now

            # Append to heartbeats table
            heartbeat = DeviceHeartbeat(
                device_id=device.id,
                child_profile_id=child_id,
                battery_percent=payload.battery_percent,
                is_charging=payload.is_charging or False,
                network_type=payload.network_type,
                storage_free_mb=payload.storage_free_mb,
                is_gps_enabled=payload.is_gps_enabled if payload.is_gps_enabled is not None else True,
                observed_at=ensure_utc(payload.observed_at),
                received_at=now,
            )
            db.add(heartbeat)

    db.commit()

    return DeviceStatusUploadResponse(
        status="recorded",
        child_profile_id=child_id,
        device_id=target_device_id,
        received_at=now,
    )


@router.get(
    "/{child_id}/status",
    response_model=ChildDeviceStatusResponse,
    summary="Get Child Device Status and Telemetry",
    description="Retrieve live telemetry and connectivity status for all registered devices of an authorized child.",
)
def get_child_device_status(
    child_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    child = verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)
    now = utc_now()

    devices = (
        db.query(RegisteredDevice)
        .filter(RegisteredDevice.child_profile_id == child_id)
        .all()
    )

    summaries: List[DeviceTelemetrySummary] = []
    for dev in devices:
        # Determine if online (checked in within last 5 minutes / 300 seconds)
        is_online = False
        if dev.last_seen_at:
            age_s = (now - ensure_utc(dev.last_seen_at)).total_seconds()
            is_online = (age_s <= 300)

        # Get latest heartbeat for network_type & is_gps_enabled
        latest_hb = (
            db.query(DeviceHeartbeat)
            .filter(DeviceHeartbeat.device_id == dev.id)
            .order_by(DeviceHeartbeat.observed_at.desc())
            .first()
        )

        summaries.append(
            DeviceTelemetrySummary(
                device_id=dev.id,
                device_identifier=dev.device_identifier,
                device_model=dev.device_model,
                battery_percent=dev.battery_percent,
                is_charging=dev.is_charging,
                network_type=latest_hb.network_type if latest_hb else None,
                location_permission_state=dev.location_permission_state,
                is_gps_enabled=latest_hb.is_gps_enabled if latest_hb else True,
                is_online=is_online,
                last_seen_at=dev.last_seen_at,
            )
        )

    return ChildDeviceStatusResponse(
        child_profile_id=child_id,
        sharing_enabled=child.sharing_enabled,
        devices=summaries,
        retrieved_at=now,
    )
