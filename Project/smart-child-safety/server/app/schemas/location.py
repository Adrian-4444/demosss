"""Pydantic schemas for Location Tracking and Device Telemetry."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LocationUploadRequest(BaseModel):
    """Payload submitted by a monitored child device to report its current GPS position."""

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="WGS84 latitude coordinate in degrees (-90.0 to +90.0)",
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="WGS84 longitude coordinate in degrees (-180.0 to +180.0)",
    )
    accuracy_m: Optional[float] = Field(
        None,
        ge=0.0,
        description="Estimated horizontal GPS accuracy radius in meters (non-negative)",
    )
    speed_mps: Optional[float] = Field(
        None,
        ge=0.0,
        description="Instantaneous ground speed in meters per second (non-negative)",
    )
    bearing_deg: Optional[float] = Field(
        None,
        ge=0.0,
        le=360.0,
        description="Direction of travel in degrees (0.0 to 360.0, clockwise from true North)",
    )
    altitude_m: Optional[float] = Field(
        None,
        description="Altitude in meters above the WGS84 reference ellipsoid",
    )
    captured_at: datetime = Field(
        ...,
        description="UTC timestamp when the GPS fix was acquired on the mobile device",
    )


class LocationIngestResponse(BaseModel):
    """Response returned after processing a location upload."""

    status: str = Field("success", description="Ingestion status: success or duplicate")
    record_id: str = Field(..., description="Unique UUID of the stored location record")
    child_profile_id: str = Field(..., description="Child profile UUID")
    device_id: Optional[str] = Field(None, description="Registered device UUID if reported from paired hardware")
    captured_at: datetime = Field(..., description="GPS fix capture timestamp (UTC)")
    received_at: datetime = Field(..., description="Server receipt timestamp (UTC)")
    freshness_status: str = Field(..., description="Calculated freshness: LIVE, FRESH, or STALE")
    is_latest: bool = Field(True, description="Whether this update advanced the latest known location")


class LocationPointResponse(BaseModel):
    """Detailed model representing a single GPS location point."""

    id: str
    child_profile_id: str
    device_id: Optional[str] = None
    latitude: float
    longitude: float
    accuracy_m: Optional[float] = None
    speed_mps: Optional[float] = None
    bearing_deg: Optional[float] = None
    altitude_m: Optional[float] = None
    captured_at: datetime
    received_at: datetime
    freshness_status: Optional[str] = None
    age_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class LatestLocationResponse(BaseModel):
    """Response model for retrieving the newest known location of a child."""

    child_profile_id: str
    freshness_status: str = Field(
        ...,
        description="Dynamic freshness state: LIVE, FRESH, STALE, or NOT_REPORTING",
    )
    sharing_enabled: bool = Field(
        True,
        description="Whether location sharing is actively enabled for this child profile",
    )
    location: Optional[LocationPointResponse] = Field(
        None,
        description="Newest location point if available and sharing is enabled",
    )
    retrieved_at: datetime = Field(..., description="Timestamp of query execution (UTC)")


class LocationHistoryResponse(BaseModel):
    """Paginated collection of historical location points bounded by the retention window."""

    child_profile_id: str
    total: int = Field(..., ge=0, description="Total number of points matching filter criteria")
    limit: int = Field(..., ge=1, description="Page limit applied to the query")
    offset: int = Field(..., ge=0, description="Page offset applied to the query")
    retention_days: int = Field(..., description="Configured data retention period in days")
    retention_cutoff: datetime = Field(..., description="Timestamp before which records are pruned/excluded (UTC)")
    items: List[LocationPointResponse] = Field(default_factory=list, description="Ordered chronological location records")


class DeviceStatusUploadRequest(BaseModel):
    """Payload submitted by a child device to report periodic hardware telemetry."""

    battery_percent: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Current battery level percentage (0 to 100)",
    )
    is_charging: Optional[bool] = Field(
        False,
        description="True if device is currently connected to AC/USB power",
    )
    network_type: Optional[str] = Field(
        None,
        max_length=32,
        description="Active network type: WIFI, CELLULAR, or OFFLINE",
    )
    location_permission_state: Optional[str] = Field(
        "granted_always",
        max_length=64,
        description="Android OS location runtime permission status",
    )
    storage_free_mb: Optional[int] = Field(
        None,
        ge=0,
        description="Available internal storage in megabytes",
    )
    is_gps_enabled: Optional[bool] = Field(
        True,
        description="Whether GPS hardware location services are enabled on the device",
    )
    observed_at: datetime = Field(
        ...,
        description="Timestamp when telemetry metrics were captured on the device",
    )


class DeviceStatusUploadResponse(BaseModel):
    """Response returned upon persisting hardware telemetry."""

    status: str = "recorded"
    child_profile_id: str
    device_id: Optional[str] = None
    received_at: datetime


class DeviceTelemetrySummary(BaseModel):
    """Telemetry status of an individual paired device."""

    device_id: str
    device_identifier: str
    device_model: Optional[str] = None
    battery_percent: Optional[int] = None
    is_charging: Optional[bool] = None
    network_type: Optional[str] = None
    location_permission_state: str
    is_gps_enabled: bool
    is_online: bool = Field(..., description="True if device checked in within the last 5 minutes")
    last_seen_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ChildDeviceStatusResponse(BaseModel):
    """Aggregated status and telemetry for all devices assigned to a child."""

    child_profile_id: str
    sharing_enabled: bool
    devices: List[DeviceTelemetrySummary] = Field(default_factory=list)
    retrieved_at: datetime
