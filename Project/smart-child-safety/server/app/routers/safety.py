"""API router for Safe Zones, Emergency SOS Alerts, and Auditable Safety Events."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.child import ChildProfile, RegisteredDevice
from app.models.safety import SafetyEvent, SafetyZone
from app.models.user import ensure_utc, utc_now
from app.schemas.safety import (
    ALLOWED_SEVERITIES,
    ALLOWED_ZONE_TYPES,
    SafeZoneCreateRequest,
    SafeZoneResponse,
    SafeZoneUpdateRequest,
    SafetyEventAckResponse,
    SafetyEventListResponse,
    SafetyEventResponse,
    SOSCreateRequest,
    SOSResponse,
)
from app.security import (
    AuthenticatedPrincipal,
    CallerIdentity,
    get_current_principal,
    optional_bearer_scheme,
    verify_child_ingestion_auth,
    verify_guardian_child_access,
    verify_guardian_family_access,
)
from app.services import fcm
from app.websocket.manager import ws_manager

logger = logging.getLogger("app.routers.safety")
settings = get_settings()

router = APIRouter(tags=["Safety Zones & Events"])


# ==============================================================================
# S-061: Safe Zone CRUD Endpoints
# ==============================================================================


@router.post(
    "/children/{child_id}/safe-zones",
    response_model=SafeZoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Safe Zone (Guardian)",
    description=(
        "Create a circular geofence boundary (SAFE, RESTRICTED, or DANGER) for a child. "
        "Validates center coordinates [-90, 90] / [-180, 180] and radius in meters (10m to 50km)."
    ),
)
async def create_safe_zone(
    child_id: str,
    payload: SafeZoneCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Create a new safe zone geofence."""
    child = verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)

    # Associate zone with this specific child or keep family-wide if explicitly set to None
    zone_child_id = payload.child_profile_id if payload.child_profile_id is not None else child_id

    # If payload specified a child_id different from URL path, verify that child belongs to same family
    if zone_child_id and zone_child_id != child_id:
        verify_guardian_child_access(child_profile_id=zone_child_id, principal=principal, db=db)

    now = utc_now()
    zone = SafetyZone(
        family_id=child.family_id,
        child_profile_id=zone_child_id,
        name=payload.name.strip(),
        zone_type=payload.zone_type,
        center_latitude=payload.center_latitude,
        center_longitude=payload.center_longitude,
        radius_meters=payload.radius_meters,
        is_active=payload.is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)

    logger.info(
        "Created safe zone id=%s ('%s', %s) for family_id=%s, child_id=%s by user_id=%s",
        zone.id,
        zone.name,
        zone.zone_type,
        child.family_id,
        zone_child_id,
        principal.id,
    )
    return zone


@router.get(
    "/children/{child_id}/safe-zones",
    response_model=List[SafeZoneResponse],
    summary="List Safe Zones for Child (Guardian)",
    description=(
        "List all safe zones applicable to a child, including child-specific zones "
        "and family-wide active zones."
    ),
)
def list_child_safe_zones(
    child_id: str,
    include_inactive: bool = Query(False, description="Whether to include deactivated zones"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Retrieve all safe zones applicable to the specified child."""
    child = verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)

    query = db.query(SafetyZone).filter(
        SafetyZone.family_id == child.family_id,
        (SafetyZone.child_profile_id == child_id) | (SafetyZone.child_profile_id == None),
    )
    if not include_inactive:
        query = query.filter(SafetyZone.is_active == True)

    zones = query.order_by(SafetyZone.created_at.desc()).all()
    return zones


@router.get(
    "/safe-zones/{zone_id}",
    response_model=SafeZoneResponse,
    summary="Get Safe Zone by ID (Guardian)",
    description="Retrieve details of a specific safe zone. Requires active family membership.",
)
def get_safe_zone(
    zone_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Fetch safe zone details by zone ID."""
    zone = db.query(SafetyZone).filter(SafetyZone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safe zone not found",
        )

    verify_guardian_family_access(family_id=zone.family_id, principal=principal, db=db)
    return zone


@router.patch(
    "/safe-zones/{zone_id}",
    response_model=SafeZoneResponse,
    summary="Update Safe Zone (Guardian)",
    description="Partially update a safe zone's name, type, coordinates, radius, or active state.",
)
async def update_safe_zone(
    zone_id: str,
    payload: SafeZoneUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Update safe zone parameters."""
    zone = db.query(SafetyZone).filter(SafetyZone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safe zone not found",
        )

    verify_guardian_family_access(
        family_id=zone.family_id,
        principal=principal,
        db=db,
        allowed_roles=["owner", "guardian"],
    )

    if payload.name is not None:
        zone.name = payload.name.strip()
    if payload.zone_type is not None:
        zone.zone_type = payload.zone_type
    if payload.center_latitude is not None:
        zone.center_latitude = payload.center_latitude
    if payload.center_longitude is not None:
        zone.center_longitude = payload.center_longitude
    if payload.radius_meters is not None:
        zone.radius_meters = payload.radius_meters
    if payload.is_active is not None:
        zone.is_active = payload.is_active

    zone.updated_at = utc_now()
    db.commit()
    db.refresh(zone)

    logger.info("Updated safe zone id=%s by user_id=%s", zone.id, principal.id)
    return zone


@router.delete(
    "/safe-zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Safe Zone (Guardian)",
    description="Permanently delete a safe zone. Historical safety events are preserved.",
)
async def delete_safe_zone(
    zone_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Delete a safe zone."""
    zone = db.query(SafetyZone).filter(SafetyZone.id == zone_id).first()
    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safe zone not found",
        )

    verify_guardian_family_access(
        family_id=zone.family_id,
        principal=principal,
        db=db,
        allowed_roles=["owner", "guardian"],
    )

    db.delete(zone)
    db.commit()
    logger.info("Deleted safe zone id=%s by user_id=%s", zone_id, principal.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==============================================================================
# S-060: Emergency SOS Endpoint
# ==============================================================================


@router.post(
    "/children/{child_id}/sos",
    response_model=SOSResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger Emergency SOS (Child Device or Guardian)",
    description=(
        "Persist emergency SOS event, suppress duplicate triggers within 60s, "
        "and attempt push notification to authorized guardians with WebSocket broadcasting."
    ),
)
async def trigger_emergency_sos(
    child_id: str,
    payload: SOSCreateRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
):
    """Handle emergency SOS button activation."""
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
    triggered_at = ensure_utc(payload.triggered_at) or now

    # S-060 Duplicate Suppression: check for unacknowledged SOS within 60-second cooldown window
    cutoff = now - timedelta(seconds=60)
    recent_sos = (
        db.query(SafetyEvent)
        .filter(
            SafetyEvent.child_profile_id == child_id,
            SafetyEvent.event_type == "SOS",
            SafetyEvent.created_at >= cutoff,
        )
        .order_by(SafetyEvent.created_at.desc())
        .first()
    )

    if recent_sos:
        logger.info(
            "Duplicate SOS within 60s window suppressed for child_id=%s (existing event_id=%s)",
            child_id,
            recent_sos.id,
        )
        return SOSResponse(
            status="duplicate_suppressed",
            event_id=recent_sos.id,
            child_profile_id=child_id,
            family_id=child.family_id,
            severity="CRITICAL",
            notification_status="attempted",
            triggered_at=recent_sos.created_at,
            received_at=now,
        )

    # 1. Persist the safety event durably FIRST
    event = SafetyEvent(
        family_id=child.family_id,
        child_profile_id=child_id,
        event_type="SOS",
        severity="CRITICAL",
        reason=payload.message or f"Emergency SOS triggered for child {child.first_name}",
        metadata_json={
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "accuracy_m": payload.accuracy_m,
            "caller_type": caller.caller_type,
            "device_id": caller.device_id,
            "message": payload.message,
            "triggered_at": triggered_at.isoformat(),
        },
        is_acknowledged=False,
        created_at=now,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    logger.warning(
        "EMERGENCY SOS PERSISTED: event_id=%s, child_id=%s, caller_type=%s",
        event.id,
        child_id,
        caller.caller_type,
    )

    # 2. Attempt push notification to all paired devices with FCM tokens
    registered_devices = (
        db.query(RegisteredDevice)
        .filter(
            RegisteredDevice.child_profile_id == child_id,
            RegisteredDevice.is_active == True,
            RegisteredDevice.fcm_token != None,
        )
        .all()
    )

    notification_attempted = False
    for dev in registered_devices:
        if dev.fcm_token:
            try:
                fcm.send_fcm_notification(
                    target_token=dev.fcm_token,
                    title="EMERGENCY SOS ALERT",
                    body=f"Emergency SOS triggered for child {child.first_name}!",
                    data={
                        "action": "SOS_ALERT",
                        "child_id": child_id,
                        "event_id": event.id,
                        "severity": "CRITICAL",
                    },
                )
                notification_attempted = True
            except Exception as exc:
                logger.warning("FCM alert delivery attempt failed for device id=%s: %s", dev.id, exc)

    # 3. Publish real-time alert to connected WebSocket subscribers
    await ws_manager.broadcast_to_child(
        child_id=child_id,
        message={
            "event": "sos_alert",
            "child_id": child_id,
            "family_id": child.family_id,
            "event_id": event.id,
            "severity": "CRITICAL",
            "message": event.reason,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "triggered_at": triggered_at.isoformat(),
            "notification_status": "attempted",
        },
    )

    return SOSResponse(
        status="persisted",
        event_id=event.id,
        child_profile_id=child_id,
        family_id=child.family_id,
        severity="CRITICAL",
        notification_status="attempted",
        triggered_at=triggered_at,
        received_at=now,
    )


# ==============================================================================
# S-063: Safety Events Listing & Acknowledgement
# ==============================================================================


@router.get(
    "/children/{child_id}/events",
    response_model=SafetyEventListResponse,
    summary="List Safety Events for Child (Guardian)",
    description=(
        "Retrieve auditable safety events (SOS, ZONE_ENTRY, ZONE_EXIT) for an authorized child. "
        "Supports pagination and filtering by event_type, severity, and acknowledgement status."
    ),
)
def list_child_safety_events(
    child_id: str,
    limit: int = Query(50, ge=1, le=100, description="Page limit (1-100)"),
    offset: int = Query(0, ge=0, description="Page offset"),
    event_type: Optional[str] = Query(None, description="Optional filter by event_type (e.g. SOS, ZONE_ENTRY, ZONE_EXIT)"),
    severity: Optional[str] = Query(None, description="Optional filter by severity (INFO, LOW, MEDIUM, HIGH, CRITICAL)"),
    is_acknowledged: Optional[bool] = Query(None, description="Optional filter by acknowledgement status"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Query paginated safety events for an authorized child."""
    child = verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)

    query = db.query(SafetyEvent).filter(SafetyEvent.child_profile_id == child_id)

    if event_type:
        query = query.filter(SafetyEvent.event_type == event_type.strip().upper())
    if severity:
        clean_sev = severity.strip().upper()
        if clean_sev in ALLOWED_SEVERITIES:
            query = query.filter(SafetyEvent.severity == clean_sev)
    if is_acknowledged is not None:
        query = query.filter(SafetyEvent.is_acknowledged == is_acknowledged)

    total = query.count()
    items = query.order_by(SafetyEvent.created_at.desc()).offset(offset).limit(limit).all()

    return SafetyEventListResponse(
        child_profile_id=child_id,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.post(
    "/events/{event_id}/ack",
    response_model=SafetyEventAckResponse,
    summary="Acknowledge Safety Event (Guardian)",
    description=(
        "Mark an active safety event or SOS as acknowledged by an authorized guardian. "
        "Broadcasts acknowledgement event to connected WebSockets."
    ),
)
async def acknowledge_safety_event(
    event_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Mark a safety event as acknowledged by the calling guardian."""
    event = db.query(SafetyEvent).filter(SafetyEvent.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety event not found",
        )

    # Guardian must belong to the event's family
    verify_guardian_family_access(
        family_id=event.family_id,
        principal=principal,
        db=db,
    )

    now = utc_now()
    event.is_acknowledged = True
    event.acknowledged_by_user_id = principal.id
    event.acknowledged_at = now
    db.commit()
    db.refresh(event)

    logger.info(
        "Event id=%s acknowledged by guardian user_id=%s (child_id=%s)",
        event.id,
        principal.id,
        event.child_profile_id,
    )

    # Broadcast acknowledgement over WebSocket
    await ws_manager.broadcast_to_child(
        child_id=event.child_profile_id,
        message={
            "event": "event_acknowledged",
            "child_id": event.child_profile_id,
            "event_id": event.id,
            "acknowledged_by_user_id": principal.id,
            "acknowledged_at": now.isoformat(),
        },
    )

    return SafetyEventAckResponse(
        status="acknowledged",
        event_id=event.id,
        acknowledged_by_user_id=principal.id,
        acknowledged_at=now,
    )
