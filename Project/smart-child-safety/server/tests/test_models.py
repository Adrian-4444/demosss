"""Comprehensive tests for SQLAlchemy models, relationships, cascades, and constraints."""

from datetime import date, datetime, timedelta, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ChildProfile,
    CommandAcknowledgement,
    DeviceCommand,
    DeviceHeartbeat,
    Family,
    FamilyMembership,
    LatestLocation,
    LocationRecord,
    PairingCode,
    RegisteredDevice,
    SafetyEvent,
    SafetyPolicy,
    SafetyZone,
    UserProfile,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_user_and_family_creation(db_session: Session):
    """Test UserProfile, Family, and FamilyMembership creation with relationships."""
    user = UserProfile(
        firebase_uid="fb_test_guardian_1",
        email="guardian1@example.com",
        display_name="Jane Doe",
        role="guardian",
    )
    db_session.add(user)
    db_session.commit()

    family = Family(
        name="Doe Family",
        created_by_user_id=user.id,
    )
    db_session.add(family)
    db_session.commit()

    membership = FamilyMembership(
        family_id=family.id,
        user_id=user.id,
        role="owner",
    )
    db_session.add(membership)
    db_session.commit()

    # Verify relationships
    assert user.created_families[0].id == family.id
    assert len(family.memberships) == 1
    assert family.memberships[0].user.email == "guardian1@example.com"
    assert family.creator.firebase_uid == "fb_test_guardian_1"


def test_child_profile_and_device_binding(db_session: Session):
    """Test ChildProfile and RegisteredDevice creation and back-references."""
    user = UserProfile(firebase_uid="fb_guardian_2", email="guardian2@example.com", role="guardian")
    family = Family(name="Smith Family", creator=user)
    db_session.add_all([user, family])
    db_session.commit()

    child = ChildProfile(
        family_id=family.id,
        first_name="Tommy",
        display_name="Tommy Smith",
        date_of_birth=date(2015, 6, 15),
        sharing_enabled=True,
    )
    db_session.add(child)
    db_session.commit()

    device = RegisteredDevice(
        child_profile_id=child.id,
        device_identifier="hardware-uuid-android-001",
        device_model="Pixel 8",
        os_version="Android 14",
        battery_percent=85,
        location_permission_state="granted_always",
    )
    db_session.add(device)
    db_session.commit()

    assert len(child.devices) == 1
    assert child.devices[0].device_model == "Pixel 8"
    assert device.child_profile.first_name == "Tommy"


def test_latest_and_historical_location(db_session: Session):
    """Test 1:1 LatestLocation and append-only LocationRecord entities."""
    user = UserProfile(firebase_uid="fb_guardian_3", email="guardian3@example.com", role="guardian")
    family = Family(name="Brown Family", creator=user)
    child = ChildProfile(family=family, first_name="Lily", display_name="Lily Brown")
    device = RegisteredDevice(child_profile=child, device_identifier="hardware-uuid-lily-002")
    db_session.add_all([user, family, child, device])
    db_session.commit()

    capture_time = utc_now()

    # Latest location (1:1 with ChildProfile)
    latest = LatestLocation(
        child_profile_id=child.id,
        device_id=device.id,
        latitude=12.9716,
        longitude=77.5946,
        accuracy_m=4.5,
        speed_mps=1.2,
        bearing_deg=180.0,
        captured_at=capture_time,
        freshness_status="LIVE",
    )
    db_session.add(latest)

    # Historical location record
    record = LocationRecord(
        child_profile_id=child.id,
        device_id=device.id,
        latitude=12.9716,
        longitude=77.5946,
        accuracy_m=4.5,
        captured_at=capture_time,
    )
    db_session.add(record)
    db_session.commit()

    assert child.latest_location is not None
    assert child.latest_location.latitude == 12.9716
    assert child.latest_location.freshness_status == "LIVE"
    assert len(child.location_records) == 1


def test_safety_zones_policies_and_events(db_session: Session):
    """Test SafetyZone, SafetyPolicy, and explainable SafetyEvent entities."""
    user = UserProfile(firebase_uid="fb_guardian_4", email="guardian4@example.com", role="guardian")
    family = Family(name="Taylor Family", creator=user)
    child = ChildProfile(family=family, first_name="Sam", display_name="Sam Taylor")
    db_session.add_all([user, family, child])
    db_session.commit()

    # Safety Zone
    zone = SafetyZone(
        family_id=family.id,
        child_profile_id=child.id,
        name="School Zone",
        zone_type="SAFE",
        center_latitude=12.9800,
        center_longitude=77.6000,
        radius_meters=300.0,
        is_active=True,
    )
    db_session.add(zone)

    # Safety Policy
    policy = SafetyPolicy(
        family_id=family.id,
        child_profile_id=child.id,
        policy_type="GEOFENCE_SCHEDULE",
        name="School Hours",
        configuration={"start_time": "08:30", "end_time": "15:30", "days": ["mon", "tue", "wed", "thu", "fri"]},
        is_active=True,
    )
    db_session.add(policy)
    db_session.commit()

    # Safety Event (SOS or boundary transition)
    event = SafetyEvent(
        family_id=family.id,
        child_profile_id=child.id,
        zone_id=zone.id,
        policy_id=policy.id,
        event_type="SOS",
        severity="CRITICAL",
        risk_score=95.0,
        reason="Child triggered manual emergency SOS alert from device",
        metadata_json={"latitude": 12.9810, "longitude": 77.6010, "battery": 45},
    )
    db_session.add(event)
    db_session.commit()

    assert len(child.safety_events) == 1
    assert child.safety_events[0].event_type == "SOS"
    assert child.safety_events[0].zone.name == "School Zone"
    assert child.safety_events[0].policy.name == "School Hours"
    assert child.safety_events[0].is_acknowledged is False


def test_device_commands_and_acknowledgements(db_session: Session):
    """Test DeviceCommand lifecycle and CommandAcknowledgement binding."""
    user = UserProfile(firebase_uid="fb_guardian_5", email="guardian5@example.com", role="guardian")
    family = Family(name="Clark Family", creator=user)
    child = ChildProfile(family=family, first_name="Leo", display_name="Leo Clark")
    device = RegisteredDevice(child_profile=child, device_identifier="hardware-uuid-leo-003")
    db_session.add_all([user, family, child, device])
    db_session.commit()

    cmd = DeviceCommand(
        child_profile_id=child.id,
        target_device_id=device.id,
        issued_by_user_id=user.id,
        command_type="ENABLE_APP_SAFETY_MODE",
        payload={"restricted_apps": ["gaming", "social"]},
        status="PENDING",
        expires_at=utc_now() + timedelta(hours=1),
    )
    db_session.add(cmd)
    db_session.commit()

    ack = CommandAcknowledgement(
        command_id=cmd.id,
        device_id=device.id,
        status="EXECUTED",
        execution_result="Application safety restrictions enabled successfully",
    )
    db_session.add(ack)
    db_session.commit()

    assert cmd.acknowledgement is not None
    assert cmd.acknowledgement.status == "EXECUTED"
    assert cmd.acknowledgement.execution_result.startswith("Application safety")


def test_device_heartbeat_and_pairing_code(db_session: Session):
    """Test DeviceHeartbeat telemetry and PairingCode hashed invitation storage."""
    user = UserProfile(firebase_uid="fb_guardian_6", email="guardian6@example.com", role="guardian")
    family = Family(name="Evans Family", creator=user)
    child = ChildProfile(family=family, first_name="Emma", display_name="Emma Evans")
    device = RegisteredDevice(child_profile=child, device_identifier="hardware-uuid-emma-004")
    db_session.add_all([user, family, child, device])
    db_session.commit()

    # Heartbeat
    hb = DeviceHeartbeat(
        device_id=device.id,
        child_profile_id=child.id,
        battery_percent=92,
        is_charging=True,
        network_type="WIFI",
        storage_free_mb=14500,
        is_gps_enabled=True,
        observed_at=utc_now(),
    )
    db_session.add(hb)

    # Pairing Code
    pairing = PairingCode(
        family_id=family.id,
        child_profile_id=child.id,
        created_by_user_id=user.id,
        code_hash="mock_hmac_sha256_hash_123456",
        expires_at=utc_now() + timedelta(minutes=15),
    )
    db_session.add(pairing)
    db_session.commit()

    assert len(child.heartbeats) == 1
    assert child.heartbeats[0].is_charging is True
    assert len(child.pairing_codes) == 1
    assert child.pairing_codes[0].is_claimed is False


def test_unique_constraints_and_rollback(db_session: Session):
    """Test that unique constraints raise IntegrityError and can be rolled back cleanly."""
    u1 = UserProfile(firebase_uid="duplicate_uid", email="u1@example.com")
    db_session.add(u1)
    db_session.commit()

    # Duplicate firebase_uid must raise IntegrityError
    u2 = UserProfile(firebase_uid="duplicate_uid", email="u2@example.com")
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Verify session is still healthy after rollback
    assert db_session.query(UserProfile).filter_by(firebase_uid="duplicate_uid").count() == 1


def test_unique_device_identifier_constraint(db_session: Session):
    """Test that duplicate device identifiers are rejected by the database."""
    user = UserProfile(firebase_uid="fb_user_dev", email="devuser@example.com")
    family = Family(name="Dev Family", creator=user)
    child = ChildProfile(family=family, first_name="TestChild", display_name="Test Child")
    db_session.add_all([user, family, child])
    db_session.commit()

    d1 = RegisteredDevice(child_profile_id=child.id, device_identifier="unique-dev-id-999")
    db_session.add(d1)
    db_session.commit()

    d2 = RegisteredDevice(child_profile_id=child.id, device_identifier="unique-dev-id-999")
    db_session.add(d2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_foreign_key_violation_raises(db_session: Session):
    """Test that foreign key constraint violations raise IntegrityError."""
    orphan_child = ChildProfile(
        family_id="non-existent-family-id",
        first_name="Ghost",
        display_name="Ghost Child",
    )
    db_session.add(orphan_child)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cascade_delete_child_profile(db_session: Session):
    """Test that deleting a ChildProfile cascades to its devices, locations, and events."""
    user = UserProfile(firebase_uid="fb_cascade_user", email="cascade@example.com")
    family = Family(name="Cascade Family", creator=user)
    child = ChildProfile(family=family, first_name="Alex", display_name="Alex Cascade")
    device = RegisteredDevice(child_profile=child, device_identifier="cascade-dev-id-1")
    latest = LatestLocation(child_profile=child, latitude=10.0, longitude=20.0, captured_at=utc_now())
    record = LocationRecord(child_profile=child, latitude=10.0, longitude=20.0, captured_at=utc_now())
    db_session.add_all([user, family, child, device, latest, record])
    db_session.commit()

    child_id = child.id

    # Delete child
    db_session.delete(child)
    db_session.commit()

    # Verify cascading deletion
    assert db_session.query(RegisteredDevice).filter_by(child_profile_id=child_id).count() == 0
    assert db_session.query(LatestLocation).filter_by(child_profile_id=child_id).count() == 0
    assert db_session.query(LocationRecord).filter_by(child_profile_id=child_id).count() == 0
