"""Pydantic schemas for Parent-Child Device Pairing."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PairingCodeCreateRequest(BaseModel):
    """Request to generate a single-use pairing code for a child."""

    child_profile_id: str = Field(..., description="Target ChildProfile UUID to generate pairing code for")


class PairingCodeCreateResponse(BaseModel):
    """Response containing single-use pairing code (returned only once)."""

    pairing_code: str = Field(..., description="6-character single-use alphanumeric code")
    expires_at: datetime = Field(..., description="Expiration timestamp (UTC)")
    child_profile_id: str


class PairingCodeClaimRequest(BaseModel):
    """Request submitted by child device to redeem pairing invitation."""

    pairing_code: str = Field(..., min_length=4, max_length=16, description="Alphanumeric pairing code")
    device_identifier: str = Field(..., min_length=4, max_length=128, description="Unique Android hardware or installation identifier")
    device_model: Optional[str] = Field(None, max_length=120, description="Hardware model (e.g., Pixel 8, Samsung S24)")
    os_version: Optional[str] = Field(None, max_length=64, description="Operating system version (e.g., Android 14)")
    app_version: Optional[str] = Field(None, max_length=64, description="Installed child app release version")
    fcm_token: Optional[str] = Field(None, description="FCM device push notification token")


class PairingCodeClaimResponse(BaseModel):
    """Response returned upon successful device registration and pairing."""

    status: str = "paired"
    child_profile_id: str
    family_id: str
    device_id: str
    paired_at: datetime


class DeviceSummary(BaseModel):
    """Summary of a paired device."""

    id: str
    device_identifier: str
    device_model: Optional[str] = None
    os_version: Optional[str] = None
    battery_percent: Optional[int] = None
    location_permission_state: str
    is_active: bool
    last_seen_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PairingStatusResponse(BaseModel):
    """Status of devices paired to a child profile."""

    child_profile_id: str
    has_active_device: bool
    devices: List[DeviceSummary]
