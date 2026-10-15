"""SQLAlchemy models for Device Commands, Acknowledgements, and Device Heartbeats."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base
from app.models.user import generate_uuid, utc_now


class DeviceCommand(Base):
    """Represents an auditable, persisted remote command issued to a child device."""

    __tablename__ = "device_commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    child_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    target_device_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("registered_devices.id", ondelete="SET NULL"), nullable=True, index=True)
    issued_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    command_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )  # REQUEST_LOCATION_REFRESH | SYNC_POLICIES | DEVICE_STATUS_CHECK | ENABLE_APP_SAFETY_MODE | RELEASE_APP_SAFETY_MODE
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True, nullable=False)  # PENDING | SIGNAL_SENT | ACKNOWLEDGED | EXECUTED | FAILED | EXPIRED
    fcm_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    signal_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    child_profile: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="commands")
    target_device: Mapped[Optional["RegisteredDevice"]] = relationship("RegisteredDevice", back_populates="commands")
    issued_by_user: Mapped["UserProfile"] = relationship("UserProfile")
    acknowledgement: Mapped[Optional["CommandAcknowledgement"]] = relationship("CommandAcknowledgement", back_populates="command", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_pending_device_commands", "target_device_id", "status", "expires_at"),
        Index("ix_child_commands_created_desc", "child_profile_id", created_at.desc()),
    )


class CommandAcknowledgement(Base):
    """Persisted execution result and delivery proof from the child device."""

    __tablename__ = "command_acknowledgements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    command_id: Mapped[str] = mapped_column(String(36), ForeignKey("device_commands.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("registered_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # ACKNOWLEDGED | EXECUTED | FAILED
    execution_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    command: Mapped["DeviceCommand"] = relationship("DeviceCommand", back_populates="acknowledgement")
    device: Mapped["RegisteredDevice"] = relationship("RegisteredDevice", back_populates="acknowledgements")


class DeviceHeartbeat(Base):
    """Periodic telemetry report capturing battery, connectivity, and hardware state."""

    __tablename__ = "device_heartbeats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("registered_devices.id", ondelete="CASCADE"), nullable=False, index=True)
    child_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    battery_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_charging: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    network_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # WIFI | CELLULAR | OFFLINE
    storage_free_mb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_gps_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    device: Mapped["RegisteredDevice"] = relationship("RegisteredDevice", back_populates="heartbeats")
    child_profile: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="heartbeats")

    __table_args__ = (
        Index("ix_device_heartbeats_observed_desc", "device_id", observed_at.desc()),
    )
