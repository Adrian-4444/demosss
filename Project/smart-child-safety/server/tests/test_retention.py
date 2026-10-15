"""Automated test suite for Data Retention, Deletion, and Right-to-be-Forgotten workflows (Phase 7)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.child import ChildProfile, PairingCode, RegisteredDevice
from app.models.command import DeviceCommand, DeviceHeartbeat
from app.models.location import LocationRecord
from app.models.safety import SafetyEvent
from app.models.user import Family, FamilyMembership, UserProfile
from app.services.rate_limiter import (
    location_upload_limiter,
    pairing_claim_limiter,
    pairing_create_limiter,
)
from app.services.retention import (
    prune_expired_heartbeats,
    prune_expired_location_records,
    prune_expired_pairing_codes,
    run_retention_cleanup,
)


@pytest.fixture(autouse=True)
def reset_limiters():
    """Reset rate limiters before each test."""
    location_upload_limiter.reset()
    pairing_claim_limiter.reset()
    pairing_create_limiter.reset()


def setup_retention_test_env(client: TestClient, uid: str = "fb_retention_guard_1"):
    """Set up test environment with family, child, and device."""
    claims = {"uid": uid, "email": f"{uid}@retention-test.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        headers = {"Authorization": f"Bearer token_{uid}"}

        # 1. Create family
        fam_resp = client.post("/api/v1/families", json={"name": "Retention Family"}, headers=headers)
        assert fam_resp.status_code == 201
        family_id = fam_resp.json()["family_id"]

        # 2. Create child profile
        child_resp = client.post(
            f"/api/v1/families/{family_id}/children",
            json={"first_name": "Kai", "display_name": "Kai Retention"},
            headers=headers,
        )
        assert child_resp.status_code == 201
        child_id = child_resp.json()["id"]

        # 3. Create paired device
        device_identifier = f"retention-hw-{uid}"
        pair_resp = client.post("/api/v1/pairing/create", json={"child_profile_id": child_id}, headers=headers)
        assert pair_resp.status_code == 201
        raw_code = pair_resp.json()["pairing_code"]

        claim_resp = client.post(
            "/api/v1/pairing/claim",
            json={
                "pairing_code": raw_code,
                "device_identifier": device_identifier,
                "device_model": "Pixel 9",
                "os_version": "Android 15",
                "app_version": "1.0.0",
                "fcm_token": f"fcm_token_retention_{uid}",
            },
        )
        assert claim_resp.status_code == 200
        device_id = claim_resp.json()["device_id"]

        return {
            "family_id": family_id,
            "child_id": child_id,
            "device_id": device_id,
            "device_identifier": device_identifier,
            "guardian_headers": headers,
            "guardian_claims": claims,
        }


# ==============================================================================
# 1. Retention Cleanup Pruning Tests (S-070)
# ==============================================================================


def test_retention_prune_expired_location_records(client: TestClient, db_session: Session):
    """Pruning deletes location records older than the retention boundary (30 days)."""
    env = setup_retention_test_env(client, "fb_ret_loc_1")
    child_id = env["child_id"]

    now = datetime.now(timezone.utc)

    # 1. Old record from 40 days ago (should be pruned)
    old_record = LocationRecord(
        child_profile_id=child_id,
        latitude=37.7749,
        longitude=-122.4194,
        captured_at=now - timedelta(days=40),
        received_at=now - timedelta(days=40),
    )
    # 2. Recent record from 5 days ago (should be kept)
    new_record = LocationRecord(
        child_profile_id=child_id,
        latitude=37.7750,
        longitude=-122.4195,
        captured_at=now - timedelta(days=5),
        received_at=now - timedelta(days=5),
    )
    db_session.add_all([old_record, new_record])
    db_session.commit()

    pruned = prune_expired_location_records(db_session, retention_days=30)
    db_session.commit()
    assert pruned == 1

    remaining = db_session.query(LocationRecord).filter(LocationRecord.child_profile_id == child_id).all()
    assert len(remaining) == 1
    assert remaining[0].id == new_record.id


def test_retention_prune_expired_heartbeats(client: TestClient, db_session: Session):
    """Pruning deletes device heartbeats older than retention boundary (30 days)."""
    env = setup_retention_test_env(client, "fb_ret_hb_1")
    child_id = env["child_id"]
    device_id = env["device_id"]

    now = datetime.now(timezone.utc)

    old_hb = DeviceHeartbeat(
        device_id=device_id,
        child_profile_id=child_id,
        battery_percent=85,
        observed_at=now - timedelta(days=35),
    )
    new_hb = DeviceHeartbeat(
        device_id=device_id,
        child_profile_id=child_id,
        battery_percent=90,
        observed_at=now - timedelta(days=2),
    )
    db_session.add_all([old_hb, new_hb])
    db_session.commit()


    pruned = prune_expired_heartbeats(db_session, retention_days=30)
    db_session.commit()
    assert pruned == 1

    remaining = db_session.query(DeviceHeartbeat).filter(DeviceHeartbeat.child_profile_id == child_id).all()
    assert len(remaining) == 1
    assert remaining[0].id == new_hb.id


def test_retention_prune_expired_pairing_codes(client: TestClient, db_session: Session):
    """Pruning deletes unredeemed pairing codes that have expired."""
    env = setup_retention_test_env(client, "fb_ret_pair_1")
    child_id = env["child_id"]
    family_id = env["family_id"]

    user = db_session.query(UserProfile).first()
    now = datetime.now(timezone.utc)

    # 1. Expired unclaimed code
    exp_code = PairingCode(
        family_id=family_id,
        child_profile_id=child_id,
        created_by_user_id=user.id,
        code_hash="expired_hash_123",
        is_claimed=False,
        expires_at=now - timedelta(hours=2),
        created_at=now - timedelta(hours=3),
    )
    # 2. Valid active code
    act_code = PairingCode(
        family_id=family_id,
        child_profile_id=child_id,
        created_by_user_id=user.id,
        code_hash="active_hash_456",
        is_claimed=False,
        expires_at=now + timedelta(minutes=15),
        created_at=now,
    )
    db_session.add_all([exp_code, act_code])
    db_session.commit()

    pruned = prune_expired_pairing_codes(db_session)
    db_session.commit()
    assert pruned >= 1

    # Active code remains
    valid_entry = db_session.query(PairingCode).filter(PairingCode.code_hash == "active_hash_456").first()
    assert valid_entry is not None


def test_retention_maintenance_endpoint(client: TestClient):
    """Maintenance endpoint runs complete retention cleanup and returns metrics."""
    env = setup_retention_test_env(client, "fb_ret_maint_1")
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        resp = client.post("/api/v1/maintenance/retention/cleanup?retention_days=30", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["retention_days"] == 30
        assert "pruned_location_records" in data
        assert "pruned_heartbeats" in data
        assert "pruned_pairing_codes" in data
        assert "executed_at" in data


# ==============================================================================
# 2. Deletion & Right to be Forgotten Tests (S-070)
# ==============================================================================


def test_child_profile_deletion_cascades_all_tracking_history(client: TestClient, db_session: Session):
    """Deleting a child profile permanently removes all associated tracking data and telemetry."""
    env = setup_retention_test_env(client, "fb_del_child_1")
    child_id = env["child_id"]
    family_id = env["family_id"]
    device_id = env["device_id"]
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    # Seed child tracking data: location record and safety event
    now = datetime.now(timezone.utc)
    loc = LocationRecord(
        child_profile_id=child_id,
        latitude=37.7749,
        longitude=-122.4194,
        captured_at=now,
        received_at=now,
    )
    ev = SafetyEvent(
        family_id=family_id,
        child_profile_id=child_id,
        event_type="SOS",
        severity="CRITICAL",
        reason="Test SOS",
        created_at=now,
    )
    db_session.add_all([loc, ev])
    db_session.commit()

    # 1. Guardian deletes child profile
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        del_resp = client.delete(f"/api/v1/families/{family_id}/children/{child_id}", headers=headers)
        assert del_resp.status_code == 204

    # 2. Verify cascading deletion across all tables
    assert db_session.query(ChildProfile).filter(ChildProfile.id == child_id).first() is None
    assert db_session.query(RegisteredDevice).filter(RegisteredDevice.child_profile_id == child_id).first() is None
    assert db_session.query(LocationRecord).filter(LocationRecord.child_profile_id == child_id).first() is None
    assert db_session.query(SafetyEvent).filter(SafetyEvent.child_profile_id == child_id).first() is None


def test_child_profile_settings_update(client: TestClient):
    """Guardian updates child profile settings (display name, sharing enabled)."""
    env = setup_retention_test_env(client, "fb_patch_child_1")
    child_id = env["child_id"]
    family_id = env["family_id"]
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        patch_resp = client.patch(
            f"/api/v1/families/{family_id}/children/{child_id}",
            json={
                "display_name": "Kai Updated",
                "sharing_enabled": False,
            },
            headers=headers,
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["display_name"] == "Kai Updated"
        assert data["sharing_enabled"] is False


def test_account_deactivation_right_to_be_forgotten(client: TestClient, db_session: Session):
    """Guardian deactivates their own account; subsequent requests are blocked."""
    env = setup_retention_test_env(client, "fb_del_me_1")
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        # 1. Deactivate account via DELETE /api/v1/me
        del_resp = client.delete("/api/v1/me", headers=headers)
        assert del_resp.status_code == 204

        # 2. Subsequent requests return 403 Forbidden
        blocked_resp = client.get("/api/v1/me", headers=headers)
        assert blocked_resp.status_code == 403


def test_device_revocation_clears_fcm_token_and_blocks_uploads(client: TestClient, db_session: Session):
    """Unpairing a device deactivates it, clears its FCM token, and rejects further uploads."""
    env = setup_retention_test_env(client, "fb_revoke_dev_1")
    child_id = env["child_id"]
    device_id = env["device_id"]
    device_hw = env["device_identifier"]
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        # 1. Revoke device
        rev_resp = client.delete(f"/api/v1/pairing/revoke/{child_id}/devices/{device_id}", headers=headers)
        assert rev_resp.status_code == 204

    # 2. Verify in database: is_active=False and fcm_token=None
    dev = db_session.query(RegisteredDevice).filter(RegisteredDevice.id == device_id).first()
    assert dev.is_active is False
    assert dev.fcm_token is None

    # 3. Revoked device cannot upload location
    now = datetime.now(timezone.utc)
    upload_resp = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": 37.7749, "longitude": -122.4194, "accuracy_m": 5.0, "captured_at": now.isoformat()},
        headers={"X-Device-Identifier": device_hw},
    )
    assert upload_resp.status_code == 401
