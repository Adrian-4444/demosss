"""Pydantic schemas for Safe Zones, SOS Emergency Alerts, and Safety Events."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_ZONE_TYPES = {"SAFE", "RESTRICTED", "DANGER"}
ALLOWED_SEVERITIES = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}


class SafeZoneCreateRequest(BaseModel):
    """Payload to create a circular geofence boundary."""

    name: str = Field(..., min_length=2, max_length=120, description="Name of the zone (e.g., Home, School, Lake)")
    zone_type: str = Field("SAFE", description="Zone classification: SAFE, RESTRICTED, or DANGER")
    center_latitude: float = Field(..., ge=-90.0, le=90.0, description="Center latitude coordinate")
    center_longitude: float = Field(..., ge=-180.0, le=180.0, description="Center longitude coordinate")
    radius_meters: float = Field(..., ge=10.0, le=50000.0, description="Radius in meters (10m to 50km)")
    child_profile_id: Optional[str] = Field(None, description="Optional child UUID; if null, applies family-wide")
    is_active: bool = Field(True, description="Whether the zone is actively monitored")

    @field_validator("zone_type")
    @classmethod
    def validate_zone_type(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in ALLOWED_ZONE_TYPES:
            raise ValueError(f"Invalid zone_type '{v}'. Must be one of: {sorted(ALLOWED_ZONE_TYPES)}")
        return clean


class SafeZoneUpdateRequest(BaseModel):
    """Partial update payload for a safe zone."""

    name: Optional[str] = Field(None, min_length=2, max_length=120)
    zone_type: Optional[str] = None
    center_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    center_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    radius_meters: Optional[float] = Field(None, ge=10.0, le=50000.0)
    is_active: Optional[bool] = None

    @field_validator("zone_type")
    @classmethod
    def validate_zone_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip().upper()
        if clean not in ALLOWED_ZONE_TYPES:
            raise ValueError(f"Invalid zone_type '{v}'. Must be one of: {sorted(ALLOWED_ZONE_TYPES)}")
        return clean


class SafeZoneResponse(BaseModel):
    """Details of a registered safe zone."""

    id: str
    family_id: str
    child_profile_id: Optional[str] = None
    name: str
    zone_type: str
    center_latitude: float
    center_longitude: float
    radius_meters: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SOSCreateRequest(BaseModel):
    """Payload submitted by a child device when triggering emergency SOS."""

    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Latitude at time of trigger")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Longitude at time of trigger")
    accuracy_m: Optional[float] = Field(None, ge=0.0, description="Accuracy radius in meters")
    message: Optional[str] = Field(None, max_length=500, description="Optional brief emergency note")
    triggered_at: Optional[datetime] = Field(None, description="Timestamp of SOS button press on device")


class SOSResponse(BaseModel):
    """Confirmation of an emergency SOS event recording and notification attempt."""

    status: str = Field("persisted", description="persisted or duplicate_suppressed")
    event_id: str
    child_profile_id: str
    family_id: str
    severity: str = "CRITICAL"
    notification_status: str = Field("attempted", description="attempted or pending")
    triggered_at: datetime
    received_at: datetime


class SafetyEventResponse(BaseModel):
    """Auditable safety event representation."""

    id: str
    family_id: str
    child_profile_id: str
    zone_id: Optional[str] = None
    policy_id: Optional[str] = None
    event_type: str = Field(..., description="SOS, ZONE_ENTRY, ZONE_EXIT, etc.")
    severity: str
    risk_score: Optional[float] = None
    reason: str
    metadata_json: Optional[Dict[str, Any]] = None
    is_acknowledged: bool
    acknowledged_by_user_id: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SafetyEventAckResponse(BaseModel):
    """Response confirming event acknowledgement by an authorized guardian."""

    status: str = "acknowledged"
    event_id: str
    acknowledged_by_user_id: str
    acknowledged_at: datetime


class SafetyEventListResponse(BaseModel):
    """Paginated collection of safety events for a child."""

    child_profile_id: str
    total: int
    limit: int
    offset: int
    items: List[SafetyEventResponse]
