"""API router for Remote Device Commands, Acknowledgement, and Push Signaling."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.child import ChildProfile, RegisteredDevice
from app.models.command import CommandAcknowledgement, DeviceCommand
from app.models.user import ensure_utc, utc_now
from app.schemas.command import (
    CommandAckRequest,
    CommandAckResponse,
    CommandCreateRequest,
    CommandHistoryResponse,
    CommandResponse,
    PendingCommandsResponse,
)
from app.security import (
    AuthenticatedPrincipal,
    CallerIdentity,
    get_current_principal,
    optional_bearer_scheme,
    verify_child_ingestion_auth,
    verify_guardian_child_access,
)
from app.services import fcm
from app.websocket.manager import ws_manager

logger = logging.getLogger("app.routers.command")
settings = get_settings()

router = APIRouter(tags=["Commands"])


@router.post(
    "/children/{child_id}/commands",
    response_model=CommandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue Remote Device Command (Guardian)",
    description=(
        "Authorized guardian creates an allowlisted remote command (e.g. SAFETY_CHECK, "
        "REQUEST_LOCATION_REFRESH). Persists command durably before attempting FCM signaling."
    ),
)
async def create_child_command(
    child_id: str,
    payload: CommandCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    # 1. Authorize guardian has access to this child
    child = verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)

    now = utc_now()
    expires_at = now + timedelta(seconds=payload.expiry_seconds)

    # 2. Determine target device
    target_device = None
    if payload.target_device_id:
        target_device = (
            db.query(RegisteredDevice)
            .filter(
                RegisteredDevice.id == payload.target_device_id,
                RegisteredDevice.child_profile_id == child_id,
            )
            .first()
        )
        if not target_device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target device not found or not bound to this child",
            )
    else:
        # Fall back to child's primary active device
        target_device = (
            db.query(RegisteredDevice)
            .filter(
                RegisteredDevice.child_profile_id == child_id,
                RegisteredDevice.is_active == True,
            )
            .order_by(RegisteredDevice.last_seen_at.desc().nullslast())
            .first()
        )

    # 3. S-054 Persist command to PostgreSQL FIRST
    command = DeviceCommand(
        child_profile_id=child_id,
        target_device_id=target_device.id if target_device else None,
        issued_by_user_id=principal.id,
        command_type=payload.command_type,
        payload=payload.payload,
        status="PENDING",
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    db.add(command)
    db.commit()
    db.refresh(command)

    # 4. Attempt FCM Push Signal (Best-effort wake-up notification)
    if target_device and target_device.fcm_token:
        try:
            fcm_msg_id = fcm.send_fcm_command_signal(
                target_token=target_device.fcm_token,
                child_id=child_id,
                command_id=command.id,
                command_type=command.command_type,
            )
            if fcm_msg_id:
                command.status = "SIGNAL_SENT"
                command.fcm_message_id = fcm_msg_id
                command.signal_sent_at = utc_now()
                db.commit()
                db.refresh(command)
        except Exception as exc:
            # FCM send failure MUST NOT erase or invalidate the persisted command
            logger.warning("FCM signaling failed for command id=%s: %s", command.id, exc)

    # 5. Broadcast command creation event to connected WebSocket subscribers
    await ws_manager.broadcast_to_child(
        child_id=child_id,
        message={
            "event": "command_created",
            "child_id": child_id,
            "command_id": command.id,
            "command_type": command.command_type,
            "status": command.status,
            "expires_at": command.expires_at.isoformat(),
        },
    )

    return command


@router.get(
    "/children/{child_id}/commands/pending",
    response_model=PendingCommandsResponse,
    summary="Fetch Pending Commands (Child Device or Guardian)",
    description=(
        "Retrieve currently active, unexpired commands awaiting execution on child hardware. "
        "Automatically reconciles and expires commands whose TTL has elapsed."
    ),
)
def get_pending_commands(
    child_id: str,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
):
    # Verify child device or guardian
    verify_child_ingestion_auth(
        child_id=child_id,
        request=request,
        db=db,
        credentials=credentials,
    )

    now = utc_now()

    # Automatically mark past-due pending commands as EXPIRED
    db.query(DeviceCommand).filter(
        DeviceCommand.child_profile_id == child_id,
        DeviceCommand.status.in_(["PENDING", "SIGNAL_SENT"]),
        DeviceCommand.expires_at < now,
    ).update(
        {"status": "EXPIRED", "updated_at": now},
        synchronize_session=False,
    )
    db.commit()

    # Query active pending commands
    pending_commands = (
        db.query(DeviceCommand)
        .filter(
            DeviceCommand.child_profile_id == child_id,
            DeviceCommand.status.in_(["PENDING", "SIGNAL_SENT"]),
            DeviceCommand.expires_at >= now,
        )
        .order_by(DeviceCommand.created_at.asc())
        .all()
    )

    return PendingCommandsResponse(
        child_profile_id=child_id,
        count=len(pending_commands),
        commands=pending_commands,
    )


@router.post(
    "/commands/{command_id}/ack",
    response_model=CommandAckResponse,
    summary="Acknowledge Command Execution (Child Device)",
    description=(
        "Persist device execution result (ACKNOWLEDGED, EXECUTED, or FAILED) and "
        "dispatch real-time updates to connected guardians over WebSockets."
    ),
)
@router.post(
    "/commands/{command_id}/response",
    response_model=CommandAckResponse,
    include_in_schema=False,
)
async def acknowledge_command(
    command_id: str,
    payload: CommandAckRequest,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
):
    command = db.query(DeviceCommand).filter(DeviceCommand.id == command_id).first()
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    # Verify device or guardian is authorized for this child
    caller: CallerIdentity = verify_child_ingestion_auth(
        child_id=command.child_profile_id,
        request=request,
        db=db,
        credentials=credentials,
    )

    now = utc_now()

    # S-050 Expiry check: Cannot execute expired commands
    if ensure_utc(command.expires_at) < now:
        command.status = "EXPIRED"
        command.updated_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Command has expired and can no longer be executed",
        )

    # Determine reporting device ID
    device_id = caller.device_id or command.target_device_id
    if not device_id:
        # Fall back to child primary device
        primary_dev = (
            db.query(RegisteredDevice)
            .filter(
                RegisteredDevice.child_profile_id == command.child_profile_id,
                RegisteredDevice.is_active == True,
            )
            .first()
        )
        device_id = primary_dev.id if primary_dev else "unspecified-device"

    # Persist or update acknowledgement
    ack = (
        db.query(CommandAcknowledgement)
        .filter(CommandAcknowledgement.command_id == command.id)
        .first()
    )

    ack_time = ensure_utc(payload.acknowledged_at) or now

    if ack:
        ack.status = payload.status
        ack.execution_result = payload.execution_result
        ack.error_message = payload.error_message
        ack.acknowledged_at = ack_time
        ack.received_at = now
    else:
        ack = CommandAcknowledgement(
            command_id=command.id,
            device_id=device_id,
            status=payload.status,
            execution_result=payload.execution_result,
            error_message=payload.error_message,
            acknowledged_at=ack_time,
            received_at=now,
        )
        db.add(ack)

    # Advance command lifecycle state
    command.status = payload.status
    command.updated_at = now

    db.commit()
    db.refresh(command)

    # Broadcast status change to connected guardian WebSocket sessions
    await ws_manager.broadcast_to_child(
        child_id=command.child_profile_id,
        message={
            "event": "command_status_changed",
            "child_id": command.child_profile_id,
            "command_id": command.id,
            "command_type": command.command_type,
            "status": command.status,
            "execution_result": payload.execution_result,
            "updated_at": command.updated_at.isoformat(),
        },
    )

    return CommandAckResponse(
        status="recorded",
        command_id=command.id,
        device_id=device_id,
        command_status=command.status,
        acknowledged_at=ack_time,
        received_at=now,
    )


@router.get(
    "/children/{child_id}/commands",
    response_model=CommandHistoryResponse,
    summary="Get Command History (Guardian)",
    description="Retrieve paginated history of past remote commands issued to a child.",
)
def get_child_command_history(
    child_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    verify_guardian_child_access(child_profile_id=child_id, principal=principal, db=db)

    query = db.query(DeviceCommand).filter(DeviceCommand.child_profile_id == child_id)
    if status_filter:
        query = query.filter(DeviceCommand.status == status_filter.strip().upper())

    total = query.count()
    commands = (
        query.order_by(DeviceCommand.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return CommandHistoryResponse(
        child_profile_id=child_id,
        total=total,
        limit=limit,
        offset=offset,
        commands=commands,
    )
