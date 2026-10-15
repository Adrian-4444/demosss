"""Pydantic schemas for Remote Device Commands, Acknowledgements, and Synchronization."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_COMMAND_TYPES = {
    "SAFETY_CHECK",
    "REQUEST_LOCATION_REFRESH",
    "SYNC_POLICIES",
    "DEVICE_STATUS_CHECK",
    "ENABLE_APP_SAFETY_MODE",
    "RELEASE_APP_SAFETY_MODE",
}

ALLOWED_ACK_STATUSES = {
    "ACKNOWLEDGED",
    "EXECUTED",
    "FAILED",
}


class CommandCreateRequest(BaseModel):
    """Payload submitted by an authorized guardian to issue a remote device command."""

    command_type: str = Field(
        ...,
        description="Type of command to issue (e.g. SAFETY_CHECK, REQUEST_LOCATION_REFRESH, DEVICE_STATUS_CHECK)",
    )
    payload: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional command-specific arguments or configuration",
    )
    target_device_id: Optional[str] = Field(
        None,
        description="Optional registered device UUID; defaults to the child's primary active device",
    )
    expiry_seconds: int = Field(
        default=300,
        ge=30,
        le=86400,
        description="Command time-to-live before automatic expiration (default 300s / 5 minutes)",
    )

    @field_validator("command_type")
    @classmethod
    def validate_command_type(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in ALLOWED_COMMAND_TYPES:
            raise ValueError(
                f"Invalid command_type '{v}'. Must be one of: {sorted(ALLOWED_COMMAND_TYPES)}"
            )
        return clean


class CommandResponse(BaseModel):
    """Auditable state of a persisted device command."""

    id: str
    child_profile_id: str
    target_device_id: Optional[str] = None
    issued_by_user_id: str
    command_type: str
    payload: Optional[Dict[str, Any]] = None
    status: str = Field(
        ...,
        description="Command lifecycle state: PENDING, SIGNAL_SENT, ACKNOWLEDGED, EXECUTED, FAILED, EXPIRED",
    )
    fcm_message_id: Optional[str] = None
    signal_sent_at: Optional[datetime] = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommandAckRequest(BaseModel):
    """Execution proof and status update submitted by the child device."""

    status: str = Field(
        ...,
        description="Execution status: ACKNOWLEDGED, EXECUTED, or FAILED",
    )
    execution_result: Optional[str] = Field(
        None,
        description="Optional execution output or response string",
    )
    error_message: Optional[str] = Field(
        None,
        description="Error details if command execution failed",
    )
    acknowledged_at: Optional[datetime] = Field(
        None,
        description="Device timestamp when command execution completed",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in ALLOWED_ACK_STATUSES:
            raise ValueError(
                f"Invalid acknowledgement status '{v}'. Must be one of: {sorted(ALLOWED_ACK_STATUSES)}"
            )
        return clean


class CommandAckResponse(BaseModel):
    """Confirmation of processed command acknowledgement."""

    status: str = "recorded"
    command_id: str
    device_id: str
    command_status: str
    acknowledged_at: datetime
    received_at: datetime


class PendingCommandsResponse(BaseModel):
    """Collection of currently active pending commands awaiting execution on child hardware."""

    child_profile_id: str
    count: int = Field(..., ge=0)
    commands: List[CommandResponse] = Field(default_factory=list)


class CommandHistoryResponse(BaseModel):
    """Paginated collection of past commands issued to a child profile."""

    child_profile_id: str
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    commands: List[CommandResponse] = Field(default_factory=list)
