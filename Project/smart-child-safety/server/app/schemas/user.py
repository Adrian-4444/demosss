"""Pydantic schemas for User Profiles, Families, and Memberships."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UserProfileResponse(BaseModel):
    """Schema for returning user profile details."""

    id: str
    firebase_uid: str
    email: str
    display_name: Optional[str] = None
    phone_number: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    """Permitted fields for self-service user profile update."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=120)
    phone_number: Optional[str] = Field(None, max_length=32)


class FamilyCreate(BaseModel):
    """Request schema for creating a new family group."""

    name: str = Field(..., min_length=2, max_length=120, description="Family name (e.g. 'Doe Family')")


class FamilyMembershipItem(BaseModel):
    """Membership information associated with a family."""

    family_id: str
    family_name: str
    role: str
    created_at: datetime


class ChildSummaryItem(BaseModel):
    """Summary of a child profile under an authorized family."""

    id: str
    family_id: str
    first_name: str
    last_name: Optional[str] = None
    display_name: str
    gender: Optional[str] = None
    sharing_enabled: bool
    created_at: datetime


class ChildUpdate(BaseModel):
    """Permitted fields for updating child profile settings."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=64)
    last_name: Optional[str] = Field(None, max_length=64)
    display_name: Optional[str] = Field(None, min_length=1, max_length=120)
    gender: Optional[str] = Field(None, max_length=32)
    sharing_enabled: Optional[bool] = None
    location_interval_moving: Optional[int] = Field(None, ge=10, le=3600)
    location_interval_stationary: Optional[int] = Field(None, ge=30, le=7200)


class RetentionCleanupResponse(BaseModel):
    """Metrics returned by data retention cleanup execution."""

    status: str
    retention_days: int
    pruned_location_records: int
    pruned_heartbeats: int
    pruned_pairing_codes: int
    pruned_commands: int
    executed_at: datetime


class UserProfileDetailResponse(BaseModel):
    """Comprehensive user profile including associated families and linked children."""

    profile: UserProfileResponse
    families: List[FamilyMembershipItem]
    children: List[ChildSummaryItem]

