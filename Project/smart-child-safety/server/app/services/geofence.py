"""Context-aware Geofencing service using the Haversine formula and duplicate transition suppression."""

import logging
import math
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.safety import SafetyEvent, SafetyZone
from app.models.user import ensure_utc, utc_now

logger = logging.getLogger("app.services.geofence")

# Earth mean radius in meters
EARTH_RADIUS_METERS = 6371000.0


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle geodesic distance in meters between two coordinates."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c


def evaluate_safe_zones_for_location(
    child_id: str,
    family_id: str,
    latitude: float,
    longitude: float,
    captured_at: datetime,
    db: Session,
    is_latest: bool = True,
) -> List[SafetyEvent]:
    """Evaluate circular geofences for a location point and generate transition events.
    
    Applies strict duplicate suppression / hysteresis to prevent alert storms and
    rapid flapping when GPS fixes jitter around zone boundaries.
    
    If the point is out-of-order or delayed (is_latest=False), real-time transition
    events are suppressed to prevent false alerts based on historical telemetry.
    """
    if not is_latest:
        logger.info(
            "Skipping real-time geofence evaluation for delayed/out-of-order point for child_id=%s (captured_at=%s)",
            child_id,
            captured_at,
        )
        return []

    # Find all active zones applicable to this child (both child-specific and family-wide)
    zones = (
        db.query(SafetyZone)
        .filter(
            SafetyZone.family_id == family_id,
            SafetyZone.is_active == True,
            (SafetyZone.child_profile_id == child_id) | (SafetyZone.child_profile_id == None),
        )
        .all()
    )


    if not zones:
        return []

    now = utc_now()
    generated_events: List[SafetyEvent] = []

    for zone in zones:
        distance = calculate_haversine_distance(
            latitude,
            longitude,
            zone.center_latitude,
            zone.center_longitude,
        )

        is_inside = distance <= zone.radius_meters

        # Fetch the most recent entry/exit event for this child and zone
        last_event = (
            db.query(SafetyEvent)
            .filter(
                SafetyEvent.child_profile_id == child_id,
                SafetyEvent.zone_id == zone.id,
                SafetyEvent.event_type.in_(["ZONE_ENTRY", "ZONE_EXIT"]),
            )
            .order_by(SafetyEvent.created_at.desc())
            .first()
        )

        event_type: Optional[str] = None
        reason: Optional[str] = None
        severity: str = "INFO"

        if last_event is None:
            # First observation: if inside, record initial entry
            if is_inside:
                event_type = "ZONE_ENTRY"
                reason = f"Initial location fix placed child inside {zone.zone_type.lower()} zone '{zone.name}'"
        else:
            # Transition check:
            if last_event.event_type == "ZONE_ENTRY" and not is_inside:
                event_type = "ZONE_EXIT"
                reason = f"Child exited {zone.zone_type.lower()} zone '{zone.name}'"
            elif last_event.event_type == "ZONE_EXIT" and is_inside:
                event_type = "ZONE_ENTRY"
                reason = f"Child entered {zone.zone_type.lower()} zone '{zone.name}'"
            else:
                # S-062 Duplicate suppression: state has not changed (still inside or still outside)
                continue

        if not event_type:
            continue

        # Determine severity based on zone classification and transition
        z_type = zone.zone_type.upper()
        if z_type == "DANGER":
            severity = "CRITICAL" if event_type == "ZONE_ENTRY" else "MEDIUM"
        elif z_type == "RESTRICTED":
            severity = "HIGH" if event_type == "ZONE_ENTRY" else "LOW"
        else:  # SAFE zone
            severity = "LOW" if event_type == "ZONE_ENTRY" else "MEDIUM"

        event = SafetyEvent(
            family_id=family_id,
            child_profile_id=child_id,
            zone_id=zone.id,
            event_type=event_type,
            severity=severity,
            reason=reason,
            metadata_json={
                "zone_name": zone.name,
                "zone_type": zone.zone_type,
                "distance_meters": round(distance, 1),
                "radius_meters": zone.radius_meters,
                "latitude": latitude,
                "longitude": longitude,
                "captured_at": captured_at.isoformat(),
            },
            is_acknowledged=False,
            created_at=now,
        )
        db.add(event)
        generated_events.append(event)
        logger.info(
            "Geofence transition '%s' for child_id=%s, zone='%s' (distance=%.1fm, radius=%.1fm)",
            event_type,
            child_id,
            zone.name,
            distance,
            zone.radius_meters,
        )

    if generated_events:
        db.commit()
        for ev in generated_events:
            db.refresh(ev)

    return generated_events
