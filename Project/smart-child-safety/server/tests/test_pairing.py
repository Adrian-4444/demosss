"""Automated tests for parent-child device pairing, rate-limiting, and revocation."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.child import ChildProfile, PairingCode, RegisteredDevice
from app.models.user import Family, FamilyMembership, UserProfile
from app.security import hash_pairing_code
from app.services.rate_limiter import pairing_claim_limiter, pairing_create_limiter


@pytest.fixture(autouse=True)
def reset_limiters():
    """Reset rate limiter histories before each test run."""
    pairing_claim_limiter.reset()
    pairing_create_limiter.reset()


def test_create_pairing_code_authorized_guardian(client: TestClient, db_session: Session):
    """Authorized guardian can generate a single-use pairing code."""
    guardian_claims = {"uid": "fb_pairing_guardian_1", "email": "p_guardian1@example.com"}

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=guardian_claims):
        headers = {"Authorization": "Bearer guardian_token_1"}

        # Setup family and child
        fam_resp = client.post("/api/v1/families", json={"name": "Pairing Family 1"}, headers=headers)
        fam_id = fam_resp.json()["family_id"]

        child_resp = client.post(
            f"/api/v1/families/{fam_id}/children",
            json={"first_name": "Timmy", "display_name": "Timmy"},
            headers=headers,
        )
        child_id = child_resp.json()["id"]

        # Issue pairing code
        pair_resp = client.post("/api/v1/pairing/create", json={"child_profile_id": child_id}, headers=headers)
        assert pair_resp.status_code == 201
        data = pair_resp.json()
        assert "pairing_code" in data
        assert len(data["pairing_code"]) == 6
        assert data["child_profile_id"] == child_id

        # Verify only hash is stored in database
        raw_code = data["pairing_code"]
        computed_hash = hash_pairing_code(raw_code)
        db_code = db_session.query(PairingCode).filter_by(child_profile_id=child_id).first()
        assert db_code is not None
        assert db_code.code_hash == computed_hash
        assert raw_code not in db_code.code_hash


def test_create_pairing_code_cross_guardian_denied(client: TestClient):
    """Unlinked guardian cannot create pairing code for another guardian's child."""
    # Guardian A creates child
    claims_a = {"uid": "fb_pair_user_a", "email": "userA@pairing.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims_a):
        fam_a = client.post("/api/v1/families", json={"name": "Family A"}, headers={"Authorization": "Bearer a"}).json()
        child_a = client.post(
            f"/api/v1/families/{fam_a['family_id']}/children",
            json={"first_name": "ChildA", "display_name": "Child A"},
            headers={"Authorization": "Bearer a"},
        ).json()

    # Guardian B attempts to create pairing code for Child A
    claims_b = {"uid": "fb_pair_user_b", "email": "userB@pairing.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims_b):
        resp_b = client.post(
            "/api/v1/pairing/create",
            json={"child_profile_id": child_a["id"]},
            headers={"Authorization": "Bearer b"},
        )
        assert resp_b.status_code == 403
        assert "Access denied" in resp_b.json()["detail"]


def test_claim_pairing_code_success(client: TestClient, db_session: Session):
    """Child device redeems pairing code and registers hardware identity."""
    claims = {"uid": "fb_claim_guardian", "email": "claim_g@example.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        fam = client.post("/api/v1/families", json={"name": "Claim Family"}, headers={"Authorization": "Bearer g"}).json()
        child = client.post(
            f"/api/v1/families/{fam['family_id']}/children",
            json={"first_name": "Lucas", "display_name": "Lucas"},
            headers={"Authorization": "Bearer g"},
        ).json()
        pairing = client.post(
            "/api/v1/pairing/create",
            json={"child_profile_id": child["id"]},
            headers={"Authorization": "Bearer g"},
        ).json()

    raw_code = pairing["pairing_code"]

    # Child device claims pairing code (no bearer token required during onboarding)
    claim_payload = {
        "pairing_code": raw_code,
        "device_identifier": "hardware-android-id-test-777",
        "device_model": "Samsung Galaxy S24",
        "os_version": "Android 14",
        "app_version": "1.0.0",
        "fcm_token": "mock-fcm-token-xyz-123",
    }
    claim_resp = client.post("/api/v1/pairing/claim", json=claim_payload)
    assert claim_resp.status_code == 200
    data = claim_resp.json()
    assert data["status"] == "paired"
    assert data["child_profile_id"] == child["id"]
    assert "device_id" in data

    # Verify device and pairing state in database
    device = db_session.query(RegisteredDevice).filter_by(device_identifier="hardware-android-id-test-777").first()
    assert device is not None
    assert device.child_profile_id == child["id"]
    assert device.device_model == "Samsung Galaxy S24"

    pairing_db = db_session.query(PairingCode).filter_by(child_profile_id=child["id"]).first()
    assert pairing_db.is_claimed is True
    assert pairing_db.claimed_by_device_id == device.id


def test_claim_pairing_code_already_used_fails(client: TestClient):
    """Claiming an already redeemed pairing code returns 409 Conflict."""
    claims = {"uid": "fb_reuse_guardian", "email": "reuse_g@example.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        fam = client.post("/api/v1/families", json={"name": "Reuse Family"}, headers={"Authorization": "Bearer r"}).json()
        child = client.post(
            f"/api/v1/families/{fam['family_id']}/children",
            json={"first_name": "Mia", "display_name": "Mia"},
            headers={"Authorization": "Bearer r"},
        ).json()
        pairing = client.post(
            "/api/v1/pairing/create",
            json={"child_profile_id": child["id"]},
            headers={"Authorization": "Bearer r"},
        ).json()

    raw_code = pairing["pairing_code"]
    payload = {"pairing_code": raw_code, "device_identifier": "device-id-1"}

    # First claim succeeds
    resp1 = client.post("/api/v1/pairing/claim", json=payload)
    assert resp1.status_code == 200

    # Second claim with same code fails with 409 Conflict
    resp2 = client.post("/api/v1/pairing/claim", json=payload)
    assert resp2.status_code == 409
    assert "already been redeemed" in resp2.json()["detail"].lower()


def test_claim_expired_pairing_code_fails(client: TestClient, db_session: Session):
    """Claiming an expired pairing code returns 410 Gone."""
    claims = {"uid": "fb_expire_guardian", "email": "expire_g@example.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        fam = client.post("/api/v1/families", json={"name": "Expire Family"}, headers={"Authorization": "Bearer e"}).json()
        child = client.post(
            f"/api/v1/families/{fam['family_id']}/children",
            json={"first_name": "Noah", "display_name": "Noah"},
            headers={"Authorization": "Bearer e"},
        ).json()
        pairing = client.post(
            "/api/v1/pairing/create",
            json={"child_profile_id": child["id"]},
            headers={"Authorization": "Bearer e"},
        ).json()

    raw_code = pairing["pairing_code"]

    # Manually expire code in database
    db_code = db_session.query(PairingCode).filter_by(child_profile_id=child["id"]).first()
    db_code.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.commit()

    # Attempt to claim expired code
    payload = {"pairing_code": raw_code, "device_identifier": "dev-expire-test"}
    resp = client.post("/api/v1/pairing/claim", json=payload)
    assert resp.status_code == 410
    assert "expired" in resp.json()["detail"].lower()


def test_claim_invalid_pairing_code_fails(client: TestClient):
    """Submitting a non-existent code returns 400 Bad Request."""
    payload = {"pairing_code": "INVALID99", "device_identifier": "device-fake-id"}
    resp = client.post("/api/v1/pairing/claim", json=payload)
    assert resp.status_code == 400
    assert "Invalid pairing code" in resp.json()["detail"]


def test_pairing_status_and_device_revocation(client: TestClient, db_session: Session):
    """Authorized guardian can query pairing status and revoke device association."""
    claims = {"uid": "fb_status_guardian", "email": "status_g@example.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        headers = {"Authorization": "Bearer g_token"}
        fam = client.post("/api/v1/families", json={"name": "Status Family"}, headers=headers).json()
        child = client.post(
            f"/api/v1/families/{fam['family_id']}/children",
            json={"first_name": "Zoe", "display_name": "Zoe"},
            headers=headers,
        ).json()
        pairing = client.post(
            "/api/v1/pairing/create",
            json={"child_profile_id": child["id"]},
            headers=headers,
        ).json()

        # Child claims device
        claim_resp = client.post(
            "/api/v1/pairing/claim",
            json={"pairing_code": pairing["pairing_code"], "device_identifier": "zoe-phone-99"},
        ).json()
        device_id = claim_resp["device_id"]

        # Guardian checks status
        status_resp = client.get(f"/api/v1/pairing/status/{child['id']}", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["has_active_device"] is True
        assert len(status_resp.json()["devices"]) == 1

        # Guardian revokes device
        del_resp = client.delete(f"/api/v1/pairing/revoke/{child['id']}/devices/{device_id}", headers=headers)
        assert del_resp.status_code == 204

        # Status now shows no active devices
        status_after = client.get(f"/api/v1/pairing/status/{child['id']}", headers=headers)
        assert status_after.status_code == 200
        assert status_after.json()["has_active_device"] is False


def test_rate_limiter_blocks_excessive_attempts(client: TestClient):
    """Repeated rapid attempts trigger 429 Too Many Requests."""
    payload = {"pairing_code": "WRONG1", "device_identifier": "attack-dev-id"}

    # Limit is 10 requests per minute
    statuses = []
    for _ in range(12):
        resp = client.post("/api/v1/pairing/claim", json=payload)
        statuses.append(resp.status_code)

    # At least one request must have been rejected with 429
    assert 429 in statuses
