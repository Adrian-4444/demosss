"""SQLAlchemy models for Users, Families, and Family Memberships."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_uuid() -> str:
    """Generate a random UUID4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware UTC for cross-database compatibility."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class UserProfile(Base):
    """Represents an authenticated guardian or operator user account."""

    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="guardian", nullable=False)  # guardian | operator
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    memberships: Mapped[List["FamilyMembership"]] = relationship("FamilyMembership", back_populates="user", cascade="all, delete-orphan")
    created_families: Mapped[List["Family"]] = relationship("Family", back_populates="creator")


class Family(Base):
    """Represents a family group containing guardians, children, zones, and policies."""

    __tablename__ = "families"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profiles.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    creator: Mapped["UserProfile"] = relationship("UserProfile", back_populates="created_families")
    memberships: Mapped[List["FamilyMembership"]] = relationship("FamilyMembership", back_populates="family", cascade="all, delete-orphan")
    children: Mapped[List["ChildProfile"]] = relationship("ChildProfile", back_populates="family", cascade="all, delete-orphan")
    safety_zones: Mapped[List["SafetyZone"]] = relationship("SafetyZone", back_populates="family", cascade="all, delete-orphan")
    safety_policies: Mapped[List["SafetyPolicy"]] = relationship("SafetyPolicy", back_populates="family", cascade="all, delete-orphan")
    safety_events: Mapped[List["SafetyEvent"]] = relationship("SafetyEvent", back_populates="family", cascade="all, delete-orphan")


class FamilyMembership(Base):
    """Maps a user to a family with an assigned role (e.g., owner, guardian, viewer)."""

    __tablename__ = "family_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), default="guardian", nullable=False)  # owner | guardian | viewer
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    family: Mapped["Family"] = relationship("Family", back_populates="memberships")
    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("family_id", "user_id", name="uq_family_user_membership"),
        Index("ix_family_membership_lookup", "family_id", "user_id"),
    )
