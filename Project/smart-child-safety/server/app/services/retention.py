"""Data retention, automated history pruning, and right-to-be-forgotten cleanup services."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.child import PairingCode
from app.models.command import DeviceCommand, DeviceHeartbeat
from app.models.location import LocationRecord
from app.models.user import utc_now

logger = logging.getLogger("app.services.retention")
settings = get_settings()


def prune_expired_location_records(db: Session, retention_days: int) -> int:
    """Delete location history records older than the data retention boundary."""
    cutoff = utc_now() - timedelta(days=retention_days)
    stmt = delete(LocationRecord).where(LocationRecord.captured_at < cutoff)
    result = db.execute(stmt)
    count = result.rowcount or 0
    if count > 0:
        logger.info("Pruned %d expired LocationRecord(s) older than %s (%d days)", count, cutoff, retention_days)
    return count


def prune_expired_heartbeats(db: Session, retention_days: int) -> int:
    """Delete device telemetry heartbeats older than the retention boundary."""
    cutoff = utc_now() - timedelta(days=retention_days)
    stmt = delete(DeviceHeartbeat).where(DeviceHeartbeat.observed_at < cutoff)
    result = db.execute(stmt)
    count = result.rowcount or 0
    if count > 0:
        logger.info("Pruned %d expired DeviceHeartbeat(s) older than %s (%d days)", count, cutoff, retention_days)
    return count



def prune_expired_pairing_codes(db: Session) -> int:
    """Delete unredeemed pairing codes that have expired."""
    now = utc_now()
    stmt = delete(PairingCode).where(
        PairingCode.expires_at < now,
        PairingCode.is_claimed == False,
    )
    result = db.execute(stmt)
    count = result.rowcount or 0
    if count > 0:
        logger.info("Pruned %d expired unredeemed PairingCode(s)", count)
    return count


def prune_stale_completed_commands(db: Session, retention_days: int = 30) -> int:
    """Delete closed terminal commands older than retention boundary."""
    cutoff = utc_now() - timedelta(days=retention_days)
    stmt = delete(DeviceCommand).where(
        DeviceCommand.expires_at < cutoff,
        DeviceCommand.status.in_(["EXPIRED", "FAILED", "EXECUTED"]),
    )
    result = db.execute(stmt)
    count = result.rowcount or 0
    if count > 0:
        logger.info("Pruned %d completed/expired DeviceCommand(s) older than %s", count, cutoff)
    return count


def run_retention_cleanup(db: Session, location_retention_days: int = None) -> Dict[str, Any]:
    """Execute complete data retention purge across all time-series tables.
    
    Safe, auditable, and atomic cleanup adhering to privacy requirements.
    """
    days = location_retention_days if location_retention_days is not None else settings.location_retention_days
    now = utc_now()

    pruned_locations = prune_expired_location_records(db, days)
    pruned_heartbeats = prune_expired_heartbeats(db, days)
    pruned_pairing = prune_expired_pairing_codes(db)
    pruned_commands = prune_stale_completed_commands(db, days)

    db.commit()

    return {
        "status": "success",
        "retention_days": days,
        "pruned_location_records": pruned_locations,
        "pruned_heartbeats": pruned_heartbeats,
        "pruned_pairing_codes": pruned_pairing,
        "pruned_commands": pruned_commands,
        "executed_at": now.isoformat(),
    }
