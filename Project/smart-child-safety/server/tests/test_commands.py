"""Automated test suite for Remote Device Commands, FCM push signaling, and lifecycle state transitions."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.child import ChildProfile, RegisteredDevice
from app.models.command import CommandAcknowledgement, DeviceCommand
from app.models.user import Family, FamilyMembership, UserProfile
from app.services.rate_limiter import (
    location_upload_limiter,
    pairing_claim_limiter,
    pairing_create_limiter,
)


@pytest.fixture(autouse=True)
def reset_limiters():
    """Reset rate limiter histories before each test run."""
    location_upload_limiter.reset()
    pairing_claim_limiter.reset()
    pairing_create_limiter.reset()


def setup_test_environment(client: TestClient, db: Session, uid: str = "fb_cmd_guardian_1"):
    """Helper to set up an authenticated guardian, family, child profile, and paired device with FCM token."""
    claims = {"uid": uid, "email": f"{uid}@test.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        headers = {"Authorization": f"Bearer token_{uid}"}

        # 1. Create family
        fam_resp = client.post("/api/v1/families", json={"name": "Command Family"}, headers=headers)
        assert fam_resp.status_code == 201
        family_id = fam_resp.json()["family_id"]

        # 2. Create child profile
        child_resp = client.post(
            f"/api/v1/families/{family_id}/children",
            json={"first_name": "Maya", "display_name": "Maya Test"},
            headers=headers,
        )
        assert child_resp.status_code == 201
        child_id = child_resp.json()["id"]

        # 3. Create paired device with mock FCM token
        device_identifier = f"test-cmd-hw-{uid}"
        pair_resp = client.post("/api/v1/pairing/create", json={"child_profile_id": child_id}, headers=headers)
        assert pair_resp.status_code == 201
        raw_code = pair_resp.json()["pairing_code"]

        claim_resp = client.post(
            "/api/v1/pairing/claim",
            json={
                "pairing_code": raw_code,
                "device_identifier": device_identifier,
                "device_model": "Galaxy S24",
                "os_version": "Android 14",
                "app_version": "1.0.0",
                "fcm_token": f"fcm_mock_token_for_{uid}",
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
# 1. Command Creation and Allowed Types Tests (S-050, S-051)
# ==============================================================================

def test_create_command_authorized_guardian(client: TestClient, db_session: Session):
    """Authorized guardian creates an allowlisted safety-check command."""
    setup = setup_test_environment(client, db_session, "fb_cmd_create_1")
    child_id = setup["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        # Mock FCM push to return mock message ID
        with patch("app.services.fcm.send_fcm_command_signal", return_value="fcm_msg_12345"):
            payload = {
                "command_type": "SAFETY_CHECK",
                "payload": {"reason": "Routine evening check"},
                "expiry_seconds": 600,
            }
            resp = client.post(
                f"/api/v1/children/{child_id}/commands",
                json=payload,
                headers=setup["guardian_headers"],
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["child_profile_id"] == child_id
            assert data["command_type"] == "SAFETY_CHECK"
            assert data["status"] == "SIGNAL_SENT"
            assert data["fcm_message_id"] == "fcm_msg_12345"

            # Verify persisted in database
            cmd_db = db_session.query(DeviceCommand).filter_by(id=data["id"]).first()
            assert cmd_db is not None
            assert cmd_db.status == "SIGNAL_SENT"


def test_create_command_invalid_type_rejected(client: TestClient, db_session: Session):
    """Command types outside the strict allowlist are rejected with 422."""
    setup = setup_test_environment(client, db_session, "fb_cmd_invalid_type")
    child_id = setup["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        payload = {
            "command_type": "ARBITRARY_REMOTE_EXECUTE",
            "expiry_seconds": 300,
        }
        resp = client.post(
            f"/api/v1/children/{child_id}/commands",
            json=payload,
            headers=setup["guardian_headers"],
        )
        assert resp.status_code == 422


# ==============================================================================
# 2. S-054 FCM Failure Persistence & Fallback Tests
# ==============================================================================

def test_command_persists_when_fcm_fails(client: TestClient, db_session: Session):
    """FCM send failure leaves command safely persisted in PostgreSQL with status=PENDING."""
    setup = setup_test_environment(client, db_session, "fb_cmd_fcm_fail")
    child_id = setup["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        # Mock FCM signal returning None (e.g. network failure or token error)
        with patch("app.services.fcm.send_fcm_command_signal", return_value=None):
            payload = {
                "command_type": "REQUEST_LOCATION_REFRESH",
                "expiry_seconds": 300,
            }
            resp = client.post(
                f"/api/v1/children/{child_id}/commands",
                json=payload,
                headers=setup["guardian_headers"],
            )
            assert resp.status_code == 201
            data = resp.json()
            # Command was persisted successfully despite FCM failure
            assert data["status"] == "PENDING"
            assert data["fcm_message_id"] is None

            # Verify PostgreSQL durability
            cmd_db = db_session.query(DeviceCommand).filter_by(id=data["id"]).first()
            assert cmd_db is not None
            assert cmd_db.status == "PENDING"


# ==============================================================================
# 3. Child Pending Commands Sync & Auto-Expiry Tests (S-051, S-050)
# ==============================================================================

def test_child_device_sync_pending_commands(client: TestClient, db_session: Session):
    """Child device fetches pending commands using its hardware identifier."""
    setup = setup_test_environment(client, db_session, "fb_cmd_child_sync")
    child_id = setup["child_id"]
    headers_device = {"X-Device-Identifier": setup["device_identifier"]}

    # Create 2 commands as guardian
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        client.post(
            f"/api/v1/children/{child_id}/commands",
            json={"command_type": "SAFETY_CHECK", "expiry_seconds": 300},
            headers=setup["guardian_headers"],
        )
        client.post(
            f"/api/v1/children/{child_id}/commands",
            json={"command_type": "DEVICE_STATUS_CHECK", "expiry_seconds": 300},
            headers=setup["guardian_headers"],
        )

    # Child device syncs pending commands
    resp = client.get(f"/api/v1/children/{child_id}/commands/pending", headers=headers_device)
    assert resp.status_code == 200
    data = resp.json()
    assert data["child_profile_id"] == child_id
    assert data["count"] == 2
    types = [c["command_type"] for c in data["commands"]]
    assert "SAFETY_CHECK" in types
    assert "DEVICE_STATUS_CHECK" in types


def test_pending_commands_auto_expire(client: TestClient, db_session: Session):
    """Pending commands whose TTL has elapsed are marked EXPIRED and excluded from sync."""
    setup = setup_test_environment(client, db_session, "fb_cmd_expire")
    child_id = setup["child_id"]
    headers_device = {"X-Device-Identifier": setup["device_identifier"]}

    now = datetime.now(timezone.utc)
    user = db_session.query(UserProfile).filter_by(firebase_uid=setup["guardian_claims"]["uid"]).first()

    # 1. Active unexpired command
    cmd_active = DeviceCommand(
        child_profile_id=child_id,
        issued_by_user_id=user.id,
        command_type="SAFETY_CHECK",
        status="PENDING",
        expires_at=now + timedelta(minutes=5),
    )
    # 2. Expired command (expired 2 minutes ago)
    cmd_expired = DeviceCommand(
        child_profile_id=child_id,
        issued_by_user_id=user.id,
        command_type="SYNC_POLICIES",
        status="PENDING",
        expires_at=now - timedelta(minutes=2),
    )
    db_session.add_all([cmd_active, cmd_expired])
    db_session.commit()

    # Child syncs pending
    resp = client.get(f"/api/v1/children/{child_id}/commands/pending", headers=headers_device)
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["commands"][0]["id"] == cmd_active.id

    # Verify expired command status was updated in database
    db_session.refresh(cmd_expired)
    assert cmd_expired.status == "EXPIRED"


# ==============================================================================
# 4. Command Acknowledgement and Response Tests (S-052)
# ==============================================================================

def test_acknowledge_command_success(client: TestClient, db_session: Session):
    """Child device submits execution proof (ACKNOWLEDGED / EXECUTED)."""
    setup = setup_test_environment(client, db_session, "fb_cmd_ack_success")
    child_id = setup["child_id"]
    headers_device = {"X-Device-Identifier": setup["device_identifier"]}

    # Create command
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        create_resp = client.post(
            f"/api/v1/children/{child_id}/commands",
            json={"command_type": "SAFETY_CHECK", "expiry_seconds": 300},
            headers=setup["guardian_headers"],
        )
        command_id = create_resp.json()["id"]

    # Child executes and acknowledges
    now = datetime.now(timezone.utc)
    ack_payload = {
        "status": "EXECUTED",
        "execution_result": "Child tapped I am safe button",
        "acknowledged_at": now.isoformat(),
    }
    resp_ack = client.post(
        f"/api/v1/commands/{command_id}/ack",
        json=ack_payload,
        headers=headers_device,
    )
    assert resp_ack.status_code == 200
    ack_data = resp_ack.json()
    assert ack_data["status"] == "recorded"
    assert ack_data["command_status"] == "EXECUTED"

    # Verify database state
    cmd_db = db_session.query(DeviceCommand).filter_by(id=command_id).first()
    assert cmd_db.status == "EXECUTED"

    ack_db = db_session.query(CommandAcknowledgement).filter_by(command_id=command_id).first()
    assert ack_db is not None
    assert ack_db.status == "EXECUTED"
    assert ack_db.execution_result == "Child tapped I am safe button"


def test_acknowledge_expired_command_returns_410(client: TestClient, db_session: Session):
    """Attempting to execute an expired command returns HTTP 410 Gone."""
    setup = setup_test_environment(client, db_session, "fb_cmd_ack_expired")
    child_id = setup["child_id"]
    headers_device = {"X-Device-Identifier": setup["device_identifier"]}

    # Insert expired command directly
    user = db_session.query(UserProfile).filter_by(firebase_uid=setup["guardian_claims"]["uid"]).first()
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    cmd = DeviceCommand(
        child_profile_id=child_id,
        issued_by_user_id=user.id,
        command_type="SAFETY_CHECK",
        status="PENDING",
        expires_at=past,
    )
    db_session.add(cmd)
    db_session.commit()

    resp = client.post(
        f"/api/v1/commands/{cmd.id}/ack",
        json={"status": "EXECUTED"},
        headers=headers_device,
    )
    assert resp.status_code == 410
    assert "Command has expired" in resp.json()["detail"]


# ==============================================================================
# 5. Command History and Authorization Denials (S-050, S-051)
# ==============================================================================

def test_command_history_pagination(client: TestClient, db_session: Session):
    """Guardian queries paginated command history with status filtering."""
    setup = setup_test_environment(client, db_session, "fb_cmd_history")
    child_id = setup["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        # Create 3 commands
        for cmd_type in ["SAFETY_CHECK", "REQUEST_LOCATION_REFRESH", "DEVICE_STATUS_CHECK"]:
            client.post(
                f"/api/v1/children/{child_id}/commands",
                json={"command_type": cmd_type, "expiry_seconds": 300},
                headers=setup["guardian_headers"],
            )

        resp = client.get(
            f"/api/v1/children/{child_id}/commands?limit=2&offset=0",
            headers=setup["guardian_headers"],
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["total"] == 3
        assert len(d["commands"]) == 2


def test_cross_guardian_cannot_issue_commands(client: TestClient, db_session: Session):
    """Guardian B cannot issue commands to Guardian A's child profile (403)."""
    setup_a = setup_test_environment(client, db_session, "fb_cmd_cross_a")
    setup_b = setup_test_environment(client, db_session, "fb_cmd_cross_b")

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup_b["guardian_claims"]):
        resp = client.post(
            f"/api/v1/children/{setup_a['child_id']}/commands",
            json={"command_type": "SAFETY_CHECK"},
            headers=setup_b["guardian_headers"],
        )
        assert resp.status_code == 403


def test_mismatched_device_cannot_ack_command(client: TestClient, db_session: Session):
    """Device paired to Child B cannot acknowledge a command issued to Child A."""
    setup_a = setup_test_environment(client, db_session, "fb_cmd_dev_a")
    setup_b = setup_test_environment(client, db_session, "fb_cmd_dev_b")

    # Guardian A creates command for Child A
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup_a["guardian_claims"]):
        c_resp = client.post(
            f"/api/v1/children/{setup_a['child_id']}/commands",
            json={"command_type": "SAFETY_CHECK"},
            headers=setup_a["guardian_headers"],
        )
        cmd_id = c_resp.json()["id"]

    # Device B attempts to acknowledge Child A's command
    headers_device_b = {"X-Device-Identifier": setup_b["device_identifier"]}
    resp = client.post(
        f"/api/v1/commands/{cmd_id}/ack",
        json={"status": "EXECUTED"},
        headers=headers_device_b,
    )
    assert resp.status_code == 403
