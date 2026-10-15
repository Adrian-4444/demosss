"""SQLAlchemy models for Child Profiles, Registered Devices, and Pairing Codes."""

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import generate_uuid, utc_now


class ChildProfile(Base):
    """Represents a monitored child profile under an authorized family."""

    __tablename__ = "child_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(64), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sharing_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    location_interval_moving: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    location_interval_stationary: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    family: Mapped["Family"] = relationship("Family", back_populates="children")
    devices: Mapped[List["RegisteredDevice"]] = relationship("RegisteredDevice", back_populates="child_profile", cascade="all, delete-orphan")
    latest_location: Mapped[Optional["LatestLocation"]] = relationship("LatestLocation", back_populates="child_profile", uselist=False, cascade="all, delete-orphan")
    location_records: Mapped[List["LocationRecord"]] = relationship("LocationRecord", back_populates="child_profile", cascade="all, delete-orphan")
    safety_events: Mapped[List["SafetyEvent"]] = relationship("SafetyEvent", back_populates="child_profile", cascade="all, delete-orphan")
    commands: Mapped[List["DeviceCommand"]] = relationship("DeviceCommand", back_populates="child_profile", cascade="all, delete-orphan")
    pairing_codes: Mapped[List["PairingCode"]] = relationship("PairingCode", back_populates="child_profile", cascade="all, delete-orphan")
    heartbeats: Mapped[List["DeviceHeartbeat"]] = relationship("DeviceHeartbeat", back_populates="child_profile", cascade="all, delete-orphan")


class RegisteredDevice(Base):
    """Represents a physical Android device bound to a child profile."""

    __tablename__ = "registered_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    child_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    device_identifier: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    device_model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    app_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    fcm_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    battery_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_charging: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    location_permission_state: Mapped[str] = mapped_column(String(64), default="granted_always", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    child_profile: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="devices")
    commands: Mapped[List["DeviceCommand"]] = relationship("DeviceCommand", back_populates="target_device")
    acknowledgements: Mapped[List["CommandAcknowledgement"]] = relationship("CommandAcknowledgement", back_populates="device")
    heartbeats: Mapped[List["DeviceHeartbeat"]] = relationship("DeviceHeartbeat", back_populates="device", cascade="all, delete-orphan")


class PairingCode(Base):
    """Represents an expiring, single-use, hashed invitation code for device onboarding."""

    __tablename__ = "pairing_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    child_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    claimed_by_device_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("registered_devices.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    child_profile: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="pairing_codes")
    claimed_device: Mapped[Optional["RegisteredDevice"]] = relationship("RegisteredDevice")

    __table_args__ = (
        Index("ix_pairing_code_active_lookup", "code_hash", "is_claimed", "expires_at"),
    )
