"""Automated test suite for Location Ingestion, Live Tracking, History, Device Status, and Authorization."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.child import ChildProfile, RegisteredDevice
from app.models.command import DeviceHeartbeat
from app.models.location import LatestLocation, LocationRecord
from app.models.user import Family, FamilyMembership, UserProfile
from app.services.rate_limiter import (
    location_upload_limiter,
    pairing_claim_limiter,
    pairing_create_limiter,
)


@pytest.fixture(autouse=True)
def reset_location_limiters():
    """Reset rate limiter histories before each test run."""
    location_upload_limiter.reset()
    pairing_claim_limiter.reset()
    pairing_create_limiter.reset()


def setup_test_family_and_child(client: TestClient, db: Session, uid: str = "fb_loc_guardian_1"):
    """Helper fixture to set up an authenticated guardian, family, child profile, and paired device."""
    claims = {"uid": uid, "email": f"{uid}@test.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        headers = {"Authorization": f"Bearer token_{uid}"}

        # 1. Create family
        fam_resp = client.post("/api/v1/families", json={"name": "Location Test Family"}, headers=headers)
        assert fam_resp.status_code == 201
        family_id = fam_resp.json()["family_id"]

        # 2. Create child profile
        child_resp = client.post(
            f"/api/v1/families/{family_id}/children",
            json={"first_name": "Leo", "display_name": "Leo Test"},
            headers=headers,
        )
        assert child_resp.status_code == 201
        child_id = child_resp.json()["id"]

        # 3. Create paired device
        device_identifier = f"test-device-hw-{uid}"
        pair_resp = client.post("/api/v1/pairing/create", json={"child_profile_id": child_id}, headers=headers)
        assert pair_resp.status_code == 201
        raw_code = pair_resp.json()["pairing_code"]

        claim_resp = client.post(
            "/api/v1/pairing/claim",
            json={
                "pairing_code": raw_code,
                "device_identifier": device_identifier,
                "device_model": "Pixel 8 Pro",
                "os_version": "Android 14",
                "app_version": "1.0.0",
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
# 1. Location Ingestion and Validation Tests
# ==============================================================================

def test_ingest_location_success_as_child_device(client: TestClient, db_session: Session):
    """Child device can ingest GPS location with X-Device-Identifier header."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_dev_1")
    child_id = setup["child_id"]
    device_ident = setup["device_identifier"]

    now = datetime.now(timezone.utc)
    captured_at = now - timedelta(seconds=15)

    headers = {"X-Device-Identifier": device_ident}
    payload = {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "accuracy_m": 8.5,
        "speed_mps": 1.2,
        "bearing_deg": 180.0,
        "altitude_m": 920.0,
        "captured_at": captured_at.isoformat(),
    }

    resp = client.post(f"/api/v1/children/{child_id}/locations", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "success"
    assert data["child_profile_id"] == child_id
    assert data["is_latest"] is True
    assert data["freshness_status"] == "LIVE"
    assert data["device_id"] == setup["device_id"]

    # Verify LatestLocation snapshot in database
    latest = db_session.query(LatestLocation).filter_by(child_profile_id=child_id).first()
    assert latest is not None
    assert latest.latitude == 12.9716
    assert latest.longitude == 77.5946
    assert latest.accuracy_m == 8.5

    # Verify immutable LocationRecord was inserted
    record = db_session.query(LocationRecord).filter_by(id=data["record_id"]).first()
    assert record is not None
    assert record.latitude == 12.9716

    # Verify device last_seen_at was updated
    dev = db_session.query(RegisteredDevice).filter_by(id=setup["device_id"]).first()
    assert dev.last_seen_at is not None


def test_ingest_location_success_as_guardian(client: TestClient, db_session: Session):
    """Authorized guardian can ingest location via Bearer token."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_guard_upload")
    child_id = setup["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        now = datetime.now(timezone.utc)
        payload = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "accuracy_m": 5.0,
            "captured_at": (now - timedelta(seconds=10)).isoformat(),
        }
        resp = client.post(
            f"/api/v1/children/{child_id}/locations",
            json=payload,
            headers=setup["guardian_headers"],
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "success"


def test_ingest_location_coordinate_bounds_validation(client: TestClient, db_session: Session):
    """Coordinates outside valid WGS84 bounds are rejected with 422."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_bounds")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}
    now = datetime.now(timezone.utc).isoformat()

    # Latitude > 90
    resp = client.post(f"/api/v1/children/{child_id}/locations", json={"latitude": 90.1, "longitude": 0.0, "captured_at": now}, headers=headers)
    assert resp.status_code == 422

    # Latitude < -90
    resp = client.post(f"/api/v1/children/{child_id}/locations", json={"latitude": -90.5, "longitude": 0.0, "captured_at": now}, headers=headers)
    assert resp.status_code == 422

    # Longitude > 180
    resp = client.post(f"/api/v1/children/{child_id}/locations", json={"latitude": 0.0, "longitude": 180.1, "captured_at": now}, headers=headers)
    assert resp.status_code == 422

    # Longitude < -180
    resp = client.post(f"/api/v1/children/{child_id}/locations", json={"latitude": 0.0, "longitude": -180.1, "captured_at": now}, headers=headers)
    assert resp.status_code == 422

    # Negative accuracy
    resp = client.post(f"/api/v1/children/{child_id}/locations", json={"latitude": 0.0, "longitude": 0.0, "accuracy_m": -1.0, "captured_at": now}, headers=headers)
    assert resp.status_code == 422

    # Negative speed
    resp = client.post(f"/api/v1/children/{child_id}/locations", json={"latitude": 0.0, "longitude": 0.0, "speed_mps": -0.5, "captured_at": now}, headers=headers)
    assert resp.status_code == 422

    # Bearing > 360
    resp = client.post(f"/api/v1/children/{child_id}/locations", json={"latitude": 0.0, "longitude": 0.0, "bearing_deg": 361.0, "captured_at": now}, headers=headers)
    assert resp.status_code == 422


def test_ingest_location_future_timestamp_rejected(client: TestClient, db_session: Session):
    """Timestamps exceeding 5-minute future clock drift are rejected with 422."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_future")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}

    future_time = datetime.now(timezone.utc) + timedelta(minutes=10)
    payload = {
        "latitude": 10.0,
        "longitude": 20.0,
        "captured_at": future_time.isoformat(),
    }
    resp = client.post(f"/api/v1/children/{child_id}/locations", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "cannot be in the future" in resp.json()["detail"]


def test_ingest_location_retention_window_exceeded_rejected(client: TestClient, db_session: Session):
    """Timestamps older than the 30-day retention window are rejected with 422."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_retention")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}

    ancient_time = datetime.now(timezone.utc) - timedelta(days=35)
    payload = {
        "latitude": 10.0,
        "longitude": 20.0,
        "captured_at": ancient_time.isoformat(),
    }
    resp = client.post(f"/api/v1/children/{child_id}/locations", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "data retention limit" in resp.json()["detail"]


# ==============================================================================
# 2. S-045 Duplicate and Out-of-Order Tests
# ==============================================================================

def test_ingest_duplicate_location_handling(client: TestClient, db_session: Session):
    """Retransmitted duplicate points return status='duplicate' without duplicate DB entries."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_dupe")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}

    fixed_time = datetime.now(timezone.utc) - timedelta(minutes=2)
    payload = {
        "latitude": 12.34,
        "longitude": 56.78,
        "accuracy_m": 10.0,
        "captured_at": fixed_time.isoformat(),
    }

    # First upload
    resp1 = client.post(f"/api/v1/children/{child_id}/locations", json=payload, headers=headers)
    assert resp1.status_code == 201
    assert resp1.json()["status"] == "success"
    first_record_id = resp1.json()["record_id"]

    # Second upload with exact same captured_at and child
    resp2 = client.post(f"/api/v1/children/{child_id}/locations", json=payload, headers=headers)
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["status"] == "duplicate"
    assert data2["record_id"] == first_record_id
    assert data2["is_latest"] is False

    # Verify exactly one record in database
    count = db_session.query(LocationRecord).filter_by(child_profile_id=child_id).count()
    assert count == 1


def test_ingest_out_of_order_location_updates(client: TestClient, db_session: Session):
    """Delayed historical point is appended to history but does not regress LatestLocation."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_order")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}

    base_time = datetime.now(timezone.utc)
    t_newer = base_time - timedelta(minutes=1)
    t_older = base_time - timedelta(minutes=10)

    # 1. Newer point arrives first (e.g., live fix)
    payload_newer = {
        "latitude": 15.0,
        "longitude": 75.0,
        "captured_at": t_newer.isoformat(),
    }
    resp_new = client.post(f"/api/v1/children/{child_id}/locations", json=payload_newer, headers=headers)
    assert resp_new.status_code == 201
    assert resp_new.json()["is_latest"] is True

    # Latest location should be at 15.0, 75.0
    latest = db_session.query(LatestLocation).filter_by(child_profile_id=child_id).first()
    assert latest.latitude == 15.0

    # 2. Older, delayed point arrives second (e.g. flushed from device offline queue)
    payload_older = {
        "latitude": 14.0,
        "longitude": 74.0,
        "captured_at": t_older.isoformat(),
    }
    resp_old = client.post(f"/api/v1/children/{child_id}/locations", json=payload_older, headers=headers)
    assert resp_old.status_code == 201
    assert resp_old.json()["status"] == "success"
    assert resp_old.json()["is_latest"] is False  # Did NOT advance latest

    # Verify history has BOTH records
    count = db_session.query(LocationRecord).filter_by(child_profile_id=child_id).count()
    assert count == 2

    # Latest location should STILL be at 15.0, NOT regressed to 14.0
    db_session.refresh(latest)
    assert latest.latitude == 15.0


# ==============================================================================
# 3. Latest Location Retrieval and Dynamic Freshness
# ==============================================================================

def test_get_latest_location_not_reporting_initially(client: TestClient, db_session: Session):
    """Child without recorded location returns freshness_status='NOT_REPORTING'."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_noreport")
    child_id = setup["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        resp = client.get(f"/api/v1/children/{child_id}/location/latest", headers=setup["guardian_headers"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["freshness_status"] == "NOT_REPORTING"
        assert data["location"] is None
        assert data["sharing_enabled"] is True


def test_get_latest_location_dynamic_freshness_states(client: TestClient, db_session: Session):
    """Verify LIVE, FRESH, and STALE dynamic freshness evaluation."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_freshness")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        now = datetime.now(timezone.utc)

        # 1. LIVE point (< 60s)
        client.post(
            f"/api/v1/children/{child_id}/locations",
            json={"latitude": 10.0, "longitude": 20.0, "captured_at": (now - timedelta(seconds=20)).isoformat()},
            headers=headers,
        )
        resp_live = client.get(f"/api/v1/children/{child_id}/location/latest", headers=setup["guardian_headers"])
        assert resp_live.json()["freshness_status"] == "LIVE"

        # 2. FRESH point (5 minutes ago, <= 15 minutes)
        latest_entry = db_session.query(LatestLocation).filter_by(child_profile_id=child_id).first()
        latest_entry.captured_at = now - timedelta(minutes=5)
        db_session.commit()

        resp_fresh = client.get(f"/api/v1/children/{child_id}/location/latest", headers=setup["guardian_headers"])
        assert resp_fresh.json()["freshness_status"] == "FRESH"

        # 3. STALE point (25 minutes ago, > 15 minutes)
        latest_entry.captured_at = now - timedelta(minutes=25)
        db_session.commit()

        resp_stale = client.get(f"/api/v1/children/{child_id}/location/latest", headers=setup["guardian_headers"])
        assert resp_stale.json()["freshness_status"] == "STALE"


def test_location_sharing_disabled_behavior(client: TestClient, db_session: Session):
    """When sharing is disabled, uploads are forbidden (403) and latest queries return NOT_REPORTING."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_sharing_off")
    child_id = setup["child_id"]

    # Disable sharing on child profile
    child = db_session.query(ChildProfile).filter_by(id=child_id).first()
    child.sharing_enabled = False
    db_session.commit()

    # Attempt upload
    headers = {"X-Device-Identifier": setup["device_identifier"]}
    resp_upload = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": 10.0, "longitude": 20.0, "captured_at": datetime.now(timezone.utc).isoformat()},
        headers=headers,
    )
    assert resp_upload.status_code == 403
    assert "sharing is currently disabled" in resp_upload.json()["detail"]

    # Query latest location as guardian
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        resp_latest = client.get(f"/api/v1/children/{child_id}/location/latest", headers=setup["guardian_headers"])
        assert resp_latest.status_code == 200
        data = resp_latest.json()
        assert data["sharing_enabled"] is False
        assert data["freshness_status"] == "NOT_REPORTING"
        assert data["location"] is None


# ==============================================================================
# 4. Paginated Location History Tests
# ==============================================================================

def test_get_location_history_pagination(client: TestClient, db_session: Session):
    """Location history returns paginated, ordered time-series records."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_history")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}

    now = datetime.now(timezone.utc)
    # Insert 5 sequential location points
    for i in range(5):
        pt_time = now - timedelta(minutes=(10 - i * 2))
        client.post(
            f"/api/v1/children/{child_id}/locations",
            json={"latitude": 10.0 + i * 0.01, "longitude": 20.0 + i * 0.01, "captured_at": pt_time.isoformat()},
            headers=headers,
        )

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        # Page 1: limit=2, offset=0
        resp_p1 = client.get(
            f"/api/v1/children/{child_id}/locations?limit=2&offset=0",
            headers=setup["guardian_headers"],
        )
        assert resp_p1.status_code == 200
        d1 = resp_p1.json()
        assert d1["total"] == 5
        assert len(d1["items"]) == 2
        assert d1["items"][0]["latitude"] == 10.04  # Most recent first

        # Page 2: limit=2, offset=2
        resp_p2 = client.get(
            f"/api/v1/children/{child_id}/locations?limit=2&offset=2",
            headers=setup["guardian_headers"],
        )
        assert resp_p2.status_code == 200
        d2 = resp_p2.json()
        assert len(d2["items"]) == 2
        assert d2["items"][0]["latitude"] == 10.02


# ==============================================================================
# 5. Device Status and Telemetry Tests
# ==============================================================================

def test_device_status_upload_and_retrieval(client: TestClient, db_session: Session):
    """Child device uploads telemetry heartbeat; guardian queries online status."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_telemetry")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}

    now = datetime.now(timezone.utc)
    telemetry_payload = {
        "battery_percent": 88,
        "is_charging": True,
        "network_type": "WIFI",
        "location_permission_state": "granted_always",
        "storage_free_mb": 12400,
        "is_gps_enabled": True,
        "observed_at": now.isoformat(),
    }

    # Upload status
    resp_upload = client.post(f"/api/v1/children/{child_id}/status", json=telemetry_payload, headers=headers)
    assert resp_upload.status_code == 201
    assert resp_upload.json()["status"] == "recorded"

    # Verify RegisteredDevice was updated
    dev = db_session.query(RegisteredDevice).filter_by(id=setup["device_id"]).first()
    assert dev.battery_percent == 88
    assert dev.is_charging is True
    assert dev.last_seen_at is not None

    # Verify DeviceHeartbeat row was recorded
    hb = db_session.query(DeviceHeartbeat).filter_by(device_id=setup["device_id"]).first()
    assert hb is not None
    assert hb.battery_percent == 88
    assert hb.network_type == "WIFI"

    # Guardian queries status
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        resp_status = client.get(f"/api/v1/children/{child_id}/status", headers=setup["guardian_headers"])
        assert resp_status.status_code == 200
        status_data = resp_status.json()
        assert status_data["child_profile_id"] == child_id
        assert len(status_data["devices"]) == 1
        d_summary = status_data["devices"][0]
        assert d_summary["battery_percent"] == 88
        assert d_summary["is_charging"] is True
        assert d_summary["is_online"] is True
        assert d_summary["network_type"] == "WIFI"


# ==============================================================================
# 6. Authorization and Cross-Guardian Denials
# ==============================================================================

def test_unauthenticated_requests_denied(client: TestClient):
    """Requests without device identifier or Bearer token are denied (401)."""
    fake_child_id = "00000000-0000-0000-0000-000000000000"
    now = datetime.now(timezone.utc).isoformat()

    # Upload location without auth
    resp = client.post(f"/api/v1/children/{fake_child_id}/locations", json={"latitude": 10.0, "longitude": 20.0, "captured_at": now})
    assert resp.status_code == 401

    # Upload status without auth
    resp = client.post(f"/api/v1/children/{fake_child_id}/status", json={"observed_at": now})
    assert resp.status_code == 401


def test_invalid_or_deactivated_device_identifier_denied(client: TestClient, db_session: Session):
    """Non-existent or deactivated device identifiers cannot upload location."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_deact")
    child_id = setup["child_id"]
    now = datetime.now(timezone.utc).isoformat()

    # Non-existent identifier
    resp_fake = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": 10.0, "longitude": 20.0, "captured_at": now},
        headers={"X-Device-Identifier": "completely-fake-hardware-id"},
    )
    assert resp_fake.status_code == 401

    # Deactivated device
    dev = db_session.query(RegisteredDevice).filter_by(id=setup["device_id"]).first()
    dev.is_active = False
    db_session.commit()

    resp_deact = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": 10.0, "longitude": 20.0, "captured_at": now},
        headers={"X-Device-Identifier": setup["device_identifier"]},
    )
    assert resp_deact.status_code == 401


def test_mismatched_device_child_denied(client: TestClient, db_session: Session):
    """Device registered to Child A cannot upload location for Child B (403)."""
    setup_a = setup_test_family_and_child(client, db_session, "fb_loc_mismatch_a")
    setup_b = setup_test_family_and_child(client, db_session, "fb_loc_mismatch_b")

    # Device A attempts to upload for Child B
    headers_a = {"X-Device-Identifier": setup_a["device_identifier"]}
    now = datetime.now(timezone.utc).isoformat()

    resp = client.post(
        f"/api/v1/children/{setup_b['child_id']}/locations",
        json={"latitude": 10.0, "longitude": 20.0, "captured_at": now},
        headers=headers_a,
    )
    assert resp.status_code == 403
    assert "not authorized for this child profile" in resp.json()["detail"]


def test_cross_guardian_cannot_access_child_location_or_status(client: TestClient, db_session: Session):
    """Unlinked guardian cannot view latest location, history, or status of another family's child."""
    setup_a = setup_test_family_and_child(client, db_session, "fb_loc_cross_a")
    setup_b = setup_test_family_and_child(client, db_session, "fb_loc_cross_b")

    # Guardian B attempts to access Child A data
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup_b["guardian_claims"]):
        # Latest location
        resp_latest = client.get(
            f"/api/v1/children/{setup_a['child_id']}/location/latest",
            headers=setup_b["guardian_headers"],
        )
        assert resp_latest.status_code == 403

        # History
        resp_history = client.get(
            f"/api/v1/children/{setup_a['child_id']}/locations",
            headers=setup_b["guardian_headers"],
        )
        assert resp_history.status_code == 403

        # Status
        resp_status = client.get(
            f"/api/v1/children/{setup_a['child_id']}/status",
            headers=setup_b["guardian_headers"],
        )
        assert resp_status.status_code == 403


def test_location_rate_limiter_blocks_excessive_uploads(client: TestClient, db_session: Session):
    """Exceeding 120 location uploads in 60 seconds returns 429 Too Many Requests."""
    setup = setup_test_family_and_child(client, db_session, "fb_loc_rate_limit")
    child_id = setup["child_id"]
    headers = {"X-Device-Identifier": setup["device_identifier"]}

    now = datetime.now(timezone.utc)

    # Fast-forward rate limiter to max requests (120)
    for _ in range(120):
        location_upload_limiter.check("location_upload_testclient")

    # 121st upload triggers 429
    resp = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": 10.0, "longitude": 20.0, "captured_at": now.isoformat()},
        headers=headers,
    )
    assert resp.status_code == 429
    assert "Too many requests" in resp.json()["detail"]
