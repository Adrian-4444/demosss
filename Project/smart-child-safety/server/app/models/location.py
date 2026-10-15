"""SQLAlchemy models for Latest Location and Historical Location Records."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import generate_uuid, utc_now


class LatestLocation(Base):
    """Stores the single newest valid location point per child for O(1) live status lookup."""

    __tablename__ = "latest_locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    child_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("child_profiles.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    device_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("registered_devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_mps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bearing_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    altitude_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(32), default="FRESH", nullable=False)

    # Relationships
    child_profile: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="latest_location")
    device: Mapped[Optional["RegisteredDevice"]] = relationship("RegisteredDevice")


class LocationRecord(Base):
    """Immutable, append-only time-series GPS point for route analysis and retention pruning."""

    __tablename__ = "location_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    child_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("child_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    device_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("registered_devices.id", ondelete="SET NULL"),
        nullable=True,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_mps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bearing_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    altitude_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    child_profile: Mapped["ChildProfile"] = relationship("ChildProfile", back_populates="location_records")
    device: Mapped[Optional["RegisteredDevice"]] = relationship("RegisteredDevice")

    __table_args__ = (
        Index("ix_location_child_captured_desc", "child_profile_id", captured_at.desc()),
    )
