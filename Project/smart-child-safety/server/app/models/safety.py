"""SQLAlchemy models for Safety Zones, Safety Policies, and Safety Events."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base
from app.models.user import generate_uuid, utc_now


class SafetyZone(Base):
    """Represents a circular safe or restricted geofence zone defined by a guardian."""

    __tablename__ = "safety_zones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    child_profile_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(32), default="SAFE", nullable=False)  # SAFE | RESTRICTED | DANGER
    center_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    center_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    family: Mapped["Family"] = relationship("Family", back_populates="safety_zones")
    events: Mapped[List["SafetyEvent"]] = relationship("SafetyEvent", back_populates="zone")

    __table_args__ = (
        Index("ix_safety_zone_active_family", "family_id", "is_active"),
    )


class SafetyPolicy(Base):
    """Represents scheduled rules, usage constraints, or temporary exceptions."""

    __tablename__ = "safety_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    child_profile_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    policy_type: Mapped[str] = mapped_column(String(64), nullable=False)  # GEOFENCE_SCHEDULE | APP_USAGE_LIMIT | CURFEW | SPEED_LIMIT
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    configuration: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    family: Mapped["Family"] = relationship("Family", back_populates="safety_policies")
    events: Mapped[List["SafetyEvent"]] = relationship("SafetyEvent", back_populates="policy")


class SafetyEvent(Base):
    """Persisted, explainable safety violation, SOS trigger, or geofence transition."""

    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    child_profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("child_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("safety_zones.id", ondelete="SET NULL"), nullable=True, index=True)
    policy_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("safety_policies.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SOS | ZONE_ENTRY | ZONE_EXIT | ZONE_VIOLATION | etc.
    severity: Mapped[str] = mapped_column(String(32), default="INFO", nullable=False)  # INFO | LOW | MEDIUM | HIGH | CRITICAL
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("user_profiles.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True, nullable=False)

    # Relationships
    family: Mapped["Family"] = relationship("Family", back_populates="safety_events")
    child_profile: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="safety_events")
    zone: Mapped[Optional["SafetyZone"]] = relationship("SafetyZone", back_populates="events")
    policy: Mapped[Optional["SafetyPolicy"]] = relationship("SafetyPolicy", back_populates="events")
    acknowledged_by_user: Mapped[Optional["UserProfile"]] = relationship("UserProfile")

    __table_args__ = (
        Index("ix_safety_events_child_created_desc", "child_profile_id", created_at.desc()),
    )
