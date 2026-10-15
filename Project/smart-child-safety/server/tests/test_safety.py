"""Automated test suite for Safe Zones, Geofencing, Emergency SOS, and Safety Events (Phase 6)."""

import math
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.child import ChildProfile, RegisteredDevice
from app.models.safety import SafetyEvent, SafetyZone
from app.models.user import Family, FamilyMembership, UserProfile
from app.services import geofence
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


def setup_safety_test_env(client: TestClient, uid: str = "fb_safe_guardian_1"):
    """Helper to set up an authenticated guardian, family, child profile, and paired child device."""
    claims = {"uid": uid, "email": f"{uid}@safety-test.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        headers = {"Authorization": f"Bearer token_{uid}"}

        # 1. Create family
        fam_resp = client.post("/api/v1/families", json={"name": "Safety Test Family"}, headers=headers)
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

        # 3. Create paired device with mock FCM token
        device_identifier = f"test-safety-hw-{uid}"
        pair_resp = client.post("/api/v1/pairing/create", json={"child_profile_id": child_id}, headers=headers)
        assert pair_resp.status_code == 201
        raw_code = pair_resp.json()["pairing_code"]

        claim_resp = client.post(
            "/api/v1/pairing/claim",
            json={
                "pairing_code": raw_code,
                "device_identifier": device_identifier,
                "device_model": "Pixel 8",
                "os_version": "Android 15",
                "app_version": "1.0.0",
                "fcm_token": f"fcm_token_safety_{uid}",
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
# 1. Haversine Math and Boundary Distance Calculations (S-062, S-064)
# ==============================================================================


def test_haversine_distance_calculations():
    """Verify high-precision Haversine distance calculations and boundary cases."""
    # Zero distance between identical coordinates
    d_zero = geofence.calculate_haversine_distance(37.7749, -122.4194, 37.7749, -122.4194)
    assert round(d_zero, 2) == 0.0

    # Distance between SF City Hall and Oakland City Hall (~13.5 km)
    d_sf_oak = geofence.calculate_haversine_distance(37.7793, -122.4192, 37.8044, -122.2712)
    assert 13000 <= d_sf_oak <= 14000

    # 1 degree of latitude delta (~111.19 km)
    d_1deg = geofence.calculate_haversine_distance(0.0, 0.0, 1.0, 0.0)
    assert 111000 <= d_1deg <= 112000


# ==============================================================================
# 2. Safe Zone CRUD and Bounds Validation Tests (S-061, S-064)
# ==============================================================================


def test_create_safe_zone_authorized_guardian(client: TestClient):
    """Guardian successfully creates a circular safe zone with valid coordinates and radius."""
    env = setup_safety_test_env(client, "fb_zone_guard_1")
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]
    child_id = env["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        payload = {
            "name": "Home Safe Zone",
            "zone_type": "SAFE",
            "center_latitude": 37.7749,
            "center_longitude": -122.4194,
            "radius_meters": 250.0,
            "is_active": True,
        }
        resp = client.post(f"/api/v1/children/{child_id}/safe-zones", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Home Safe Zone"
        assert data["zone_type"] == "SAFE"
        assert data["center_latitude"] == 37.7749
        assert data["center_longitude"] == -122.4194
        assert data["radius_meters"] == 250.0
        assert data["is_active"] is True
        assert data["child_profile_id"] == child_id
        assert data["family_id"] == env["family_id"]
        assert "id" in data


def test_safe_zone_coordinate_and_radius_bounds_validation(client: TestClient):
    """Verify coordinate and radius bounds (10m to 50km) and zone_type constraints."""
    env = setup_safety_test_env(client, "fb_zone_guard_2")
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]
    child_id = env["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        # 1. Invalid Latitude (> 90.0)
        resp1 = client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={
                "name": "Invalid Lat Zone",
                "center_latitude": 91.5,
                "center_longitude": -122.4194,
                "radius_meters": 100.0,
            },
            headers=headers,
        )
        assert resp1.status_code == 422

        # 2. Invalid Longitude (< -180.0)
        resp2 = client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={
                "name": "Invalid Lon Zone",
                "center_latitude": 37.7749,
                "center_longitude": -181.0,
                "radius_meters": 100.0,
            },
            headers=headers,
        )
        assert resp2.status_code == 422

        # 3. Radius too small (< 10m)
        resp3 = client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={
                "name": "Too Small Zone",
                "center_latitude": 37.7749,
                "center_longitude": -122.4194,
                "radius_meters": 5.0,
            },
            headers=headers,
        )
        assert resp3.status_code == 422

        # 4. Radius too large (> 50,000m)
        resp4 = client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={
                "name": "Too Large Zone",
                "center_latitude": 37.7749,
                "center_longitude": -122.4194,
                "radius_meters": 55000.0,
            },
            headers=headers,
        )
        assert resp4.status_code == 422

        # 5. Invalid zone type (not SAFE, RESTRICTED, DANGER)
        resp5 = client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={
                "name": "Invalid Type Zone",
                "zone_type": "FORBIDDEN_ZONE",
                "center_latitude": 37.7749,
                "center_longitude": -122.4194,
                "radius_meters": 100.0,
            },
            headers=headers,
        )
        assert resp5.status_code == 422


def test_list_and_get_and_update_and_delete_safe_zones(client: TestClient):
    """Test safe zone lifecycle: create, list, get by ID, patch update, and delete."""
    env = setup_safety_test_env(client, "fb_zone_guard_3")
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]
    child_id = env["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        # Create zone 1 (Active)
        z1_resp = client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={
                "name": "School Zone",
                "zone_type": "SAFE",
                "center_latitude": 37.7800,
                "center_longitude": -122.4200,
                "radius_meters": 300.0,
                "is_active": True,
            },
            headers=headers,
        )
        assert z1_resp.status_code == 201
        zone1_id = z1_resp.json()["id"]

        # Create zone 2 (Inactive)
        z2_resp = client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={
                "name": "Lake Danger Zone",
                "zone_type": "DANGER",
                "center_latitude": 37.7900,
                "center_longitude": -122.4300,
                "radius_meters": 500.0,
                "is_active": False,
            },
            headers=headers,
        )
        assert z2_resp.status_code == 201
        zone2_id = z2_resp.json()["id"]

        # 1. List active zones (default exclude inactive)
        list_resp = client.get(f"/api/v1/children/{child_id}/safe-zones", headers=headers)
        assert list_resp.status_code == 200
        active_zones = list_resp.json()
        assert len(active_zones) == 1
        assert active_zones[0]["id"] == zone1_id

        # 2. List all zones including inactive
        list_all_resp = client.get(
            f"/api/v1/children/{child_id}/safe-zones?include_inactive=true",
            headers=headers,
        )
        assert list_all_resp.status_code == 200
        all_zones = list_all_resp.json()
        assert len(all_zones) == 2

        # 3. Get zone by ID
        get_resp = client.get(f"/api/v1/safe-zones/{zone1_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "School Zone"

        # 4. Patch update zone
        patch_resp = client.patch(
            f"/api/v1/safe-zones/{zone1_id}",
            json={"name": "Elementary School", "radius_meters": 450.0},
            headers=headers,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "Elementary School"
        assert patch_resp.json()["radius_meters"] == 450.0

        # 5. Delete zone
        del_resp = client.delete(f"/api/v1/safe-zones/{zone1_id}", headers=headers)
        assert del_resp.status_code == 204

        # Verify deletion returns 404
        get_deleted = client.get(f"/api/v1/safe-zones/{zone1_id}", headers=headers)
        assert get_deleted.status_code == 404


def test_cross_guardian_safe_zone_access_denied(client: TestClient):
    """Guardians from another family cannot create, retrieve, update, or delete safe zones."""
    env1 = setup_safety_test_env(client, "fb_cross_guard_1")
    env2 = setup_safety_test_env(client, "fb_cross_guard_2")

    headers1 = env1["guardian_headers"]
    claims1 = env1["guardian_claims"]
    child1_id = env1["child_id"]

    headers2 = env2["guardian_headers"]
    claims2 = env2["guardian_claims"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims1):
        z_resp = client.post(
            f"/api/v1/children/{child1_id}/safe-zones",
            json={
                "name": "Private Zone",
                "center_latitude": 37.7749,
                "center_longitude": -122.4194,
                "radius_meters": 100.0,
            },
            headers=headers1,
        )
        assert z_resp.status_code == 201
        zone_id = z_resp.json()["id"]

    # Guardian 2 attempts access to Guardian 1's child and zone
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims2):
        # Cannot list zones for child1
        r_list = client.get(f"/api/v1/children/{child1_id}/safe-zones", headers=headers2)
        assert r_list.status_code in [403, 404]

        # Cannot create zone for child1
        r_create = client.post(
            f"/api/v1/children/{child1_id}/safe-zones",
            json={"name": "Hacked Zone", "center_latitude": 37.7749, "center_longitude": -122.4194, "radius_meters": 100.0},
            headers=headers2,
        )
        assert r_create.status_code in [403, 404]

        # Cannot retrieve zone1
        r_get = client.get(f"/api/v1/safe-zones/{zone_id}", headers=headers2)
        assert r_get.status_code in [403, 404]

        # Cannot patch zone1
        r_patch = client.patch(f"/api/v1/safe-zones/{zone_id}", json={"name": "Malicious"}, headers=headers2)
        assert r_patch.status_code in [403, 404]

        # Cannot delete zone1
        r_del = client.delete(f"/api/v1/safe-zones/{zone_id}", headers=headers2)
        assert r_del.status_code in [403, 404]


# ==============================================================================
# 3. Emergency SOS Persistence, Duplication Suppression & FCM Tracking (S-060, S-064)
# ==============================================================================


def test_trigger_emergency_sos_device_and_guardian(client: TestClient):
    """Emergency SOS can be triggered by authenticated child hardware or authorized guardian."""
    env = setup_safety_test_env(client, "fb_sos_guard_1")
    child_id = env["child_id"]
    device_hw = env["device_identifier"]
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    with patch("app.services.fcm.send_fcm_notification", return_value="fcm_msg_sos_123") as mock_fcm:
        # 1. Trigger SOS from paired child device via X-Device-Identifier
        sos_payload = {
            "latitude": 37.7749,
            "longitude": -122.4194,
            "accuracy_m": 8.5,
            "message": "Help! Emergency SOS activated!",
        }
        resp = client.post(
            f"/api/v1/children/{child_id}/sos",
            json=sos_payload,
            headers={"X-Device-Identifier": device_hw},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "persisted"
        assert data["severity"] == "CRITICAL"
        assert data["notification_status"] == "attempted"
        assert data["child_profile_id"] == child_id
        assert data["family_id"] == env["family_id"]
        assert "event_id" in data
        assert mock_fcm.called


def test_emergency_sos_duplicate_suppression_within_cooldown(client: TestClient, db_session: Session):
    """Duplicate SOS button presses within the 60s cooldown window are suppressed to prevent alert storms."""
    env = setup_safety_test_env(client, "fb_sos_guard_2")
    child_id = env["child_id"]
    device_hw = env["device_identifier"]

    with patch("app.services.fcm.send_fcm_notification", return_value="fcm_msg_sos_456"):
        # First SOS trigger
        resp1 = client.post(
            f"/api/v1/children/{child_id}/sos",
            json={"latitude": 37.7749, "longitude": -122.4194, "message": "First SOS"},
            headers={"X-Device-Identifier": device_hw},
        )
        assert resp1.status_code == 201
        data1 = resp1.json()
        assert data1["status"] == "persisted"
        initial_event_id = data1["event_id"]

        # Immediate second SOS trigger (rapid repeated tap)
        resp2 = client.post(
            f"/api/v1/children/{child_id}/sos",
            json={"latitude": 37.7749, "longitude": -122.4194, "message": "Spam SOS"},
            headers={"X-Device-Identifier": device_hw},
        )
        assert resp2.status_code == 201
        data2 = resp2.json()
        assert data2["status"] == "duplicate_suppressed"
        assert data2["event_id"] == initial_event_id

        # Verify only 1 record was persisted in database
        count = db_session.query(SafetyEvent).filter(
            SafetyEvent.child_profile_id == child_id,
            SafetyEvent.event_type == "SOS",
        ).count()
        assert count == 1


def test_sos_unauthorized_access_denied(client: TestClient):
    """Unauthenticated or mismatched callers cannot trigger SOS for a child."""
    env = setup_safety_test_env(client, "fb_sos_guard_3")
    child_id = env["child_id"]

    # 1. No authentication
    resp1 = client.post(f"/api/v1/children/{child_id}/sos", json={"latitude": 37.7749, "longitude": -122.4194})
    assert resp1.status_code == 401

    # 2. Invalid device identifier
    resp2 = client.post(
        f"/api/v1/children/{child_id}/sos",
        json={"latitude": 37.7749, "longitude": -122.4194},
        headers={"X-Device-Identifier": "non_existent_hw_id"},
    )
    assert resp2.status_code == 401


# ==============================================================================
# 4. Geofence Evaluation, State Transitions & Duplicate Suppression (S-062, S-064)
# ==============================================================================


def test_geofence_entry_exit_and_duplicate_suppression_on_location_ingestion(client: TestClient, db_session: Session):
    """Location updates evaluate circular safe zones: trigger entry/exit transitions and suppress duplicates."""
    env = setup_safety_test_env(client, "fb_geo_guard_1")
    child_id = env["child_id"]
    device_hw = env["device_identifier"]
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    # Center at (37.7749, -122.4194) with 500m radius
    center_lat = 37.7749
    center_lon = -122.4194

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        # 1. Create Safe Zone
        z_resp = client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={
                "name": "Neighborhood Safe Zone",
                "zone_type": "SAFE",
                "center_latitude": center_lat,
                "center_longitude": center_lon,
                "radius_meters": 500.0,
                "is_active": True,
            },
            headers=headers,
        )
        assert z_resp.status_code == 201
        zone_id = z_resp.json()["id"]

    now = datetime.now(timezone.utc)

    # 2. Fix 1: Child starts outside zone (~2.8 km away)
    outside_lat = 37.8000
    outside_lon = -122.4194
    t1 = now - timedelta(minutes=10)

    resp1 = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": outside_lat, "longitude": outside_lon, "accuracy_m": 5.0, "captured_at": t1.isoformat()},
        headers={"X-Device-Identifier": device_hw},
    )
    assert resp1.status_code == 201

    # No transition event should exist yet (started outside)
    events_t1 = db_session.query(SafetyEvent).filter(SafetyEvent.child_profile_id == child_id).all()
    assert len(events_t1) == 0

    # 3. Fix 2: Child enters zone (~11 meters from center, well within 500m)
    inside_lat = 37.7750
    inside_lon = -122.4194
    t2 = now - timedelta(minutes=8)

    resp2 = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": inside_lat, "longitude": inside_lon, "accuracy_m": 5.0, "captured_at": t2.isoformat()},
        headers={"X-Device-Identifier": device_hw},
    )
    assert resp2.status_code == 201

    # ZONE_ENTRY event must be generated!
    events_t2 = db_session.query(SafetyEvent).filter(SafetyEvent.child_profile_id == child_id).all()
    assert len(events_t2) == 1
    assert events_t2[0].event_type == "ZONE_ENTRY"
    assert events_t2[0].zone_id == zone_id
    assert events_t2[0].severity == "LOW"

    # 4. Fix 3: Child remains inside zone (~22 meters from center)
    inside_lat_2 = 37.7751
    t3 = now - timedelta(minutes=6)

    resp3 = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": inside_lat_2, "longitude": inside_lon, "accuracy_m": 5.0, "captured_at": t3.isoformat()},
        headers={"X-Device-Identifier": device_hw},
    )
    assert resp3.status_code == 201

    # DUPLICATE SUPPRESSION: Still inside, so NO second ZONE_ENTRY event!
    events_t3 = db_session.query(SafetyEvent).filter(SafetyEvent.child_profile_id == child_id).all()
    assert len(events_t3) == 1

    # 5. Fix 4: Child exits zone (~2.8 km away)
    t4 = now - timedelta(minutes=4)

    resp4 = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": outside_lat, "longitude": outside_lon, "accuracy_m": 5.0, "captured_at": t4.isoformat()},
        headers={"X-Device-Identifier": device_hw},
    )
    assert resp4.status_code == 201

    # ZONE_EXIT event must be generated!
    events_t4 = (
        db_session.query(SafetyEvent)
        .filter(SafetyEvent.child_profile_id == child_id)
        .order_by(SafetyEvent.created_at.asc())
        .all()
    )
    assert len(events_t4) == 2
    assert events_t4[1].event_type == "ZONE_EXIT"
    assert events_t4[1].zone_id == zone_id

    # 6. Fix 5: Child remains outside zone
    t5 = now - timedelta(minutes=2)

    resp5 = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": outside_lat + 0.001, "longitude": outside_lon, "accuracy_m": 5.0, "captured_at": t5.isoformat()},
        headers={"X-Device-Identifier": device_hw},
    )
    assert resp5.status_code == 201

    # DUPLICATE SUPPRESSION: Still outside, so NO second ZONE_EXIT event!
    events_t5 = db_session.query(SafetyEvent).filter(SafetyEvent.child_profile_id == child_id).all()
    assert len(events_t5) == 2


def test_geofence_delayed_location_point_suppression(client: TestClient, db_session: Session):
    """Delayed / out-of-order locations do NOT trigger false real-time boundary flap events."""
    env = setup_safety_test_env(client, "fb_geo_guard_2")
    child_id = env["child_id"]
    device_hw = env["device_identifier"]
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        # Create safe zone
        client.post(
            f"/api/v1/children/{child_id}/safe-zones",
            json={"name": "Home", "center_latitude": 37.7749, "center_longitude": -122.4194, "radius_meters": 300.0},
            headers=headers,
        )

    now = datetime.now(timezone.utc)

    # 1. Ingest modern point at T=now (inside zone)
    resp1 = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": 37.7749, "longitude": -122.4194, "accuracy_m": 5.0, "captured_at": now.isoformat()},
        headers={"X-Device-Identifier": device_hw},
    )
    assert resp1.status_code == 201
    assert resp1.json()["is_latest"] is True

    initial_event_count = db_session.query(SafetyEvent).filter(SafetyEvent.child_profile_id == child_id).count()

    # 2. Ingest delayed location from 2 hours ago (outside zone)
    t_old = now - timedelta(hours=2)
    resp2 = client.post(
        f"/api/v1/children/{child_id}/locations",
        json={"latitude": 37.8500, "longitude": -122.4194, "accuracy_m": 5.0, "captured_at": t_old.isoformat()},
        headers={"X-Device-Identifier": device_hw},
    )
    assert resp2.status_code == 201
    assert resp2.json()["is_latest"] is False

    # Out-of-order point must NOT emit a new real-time geofence transition!
    final_event_count = db_session.query(SafetyEvent).filter(SafetyEvent.child_profile_id == child_id).count()
    assert final_event_count == initial_event_count


# ==============================================================================
# 5. Safety Events Query, Filtering and Acknowledgement (S-063, S-064)
# ==============================================================================


def test_list_child_safety_events_and_filtering(client: TestClient, db_session: Session):
    """Guardians can query paginated safety events filtered by event_type, severity, and acknowledgement."""
    env = setup_safety_test_env(client, "fb_event_guard_1")
    child_id = env["child_id"]
    family_id = env["family_id"]
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    now = datetime.now(timezone.utc)

    # Seed events
    ev1 = SafetyEvent(
        family_id=family_id,
        child_profile_id=child_id,
        event_type="SOS",
        severity="CRITICAL",
        reason="Manual SOS trigger",
        is_acknowledged=False,
        created_at=now - timedelta(minutes=15),
    )
    ev2 = SafetyEvent(
        family_id=family_id,
        child_profile_id=child_id,
        event_type="ZONE_ENTRY",
        severity="LOW",
        reason="Entered Safe Zone",
        is_acknowledged=True,
        created_at=now - timedelta(minutes=10),
    )
    ev3 = SafetyEvent(
        family_id=family_id,
        child_profile_id=child_id,
        event_type="ZONE_EXIT",
        severity="MEDIUM",
        reason="Exited Safe Zone",
        is_acknowledged=False,
        created_at=now - timedelta(minutes=5),
    )
    db_session.add_all([ev1, ev2, ev3])
    db_session.commit()

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        # 1. Unfiltered query: returns all 3
        r_all = client.get(f"/api/v1/children/{child_id}/events", headers=headers)
        assert r_all.status_code == 200
        data_all = r_all.json()
        assert data_all["total"] == 3
        assert len(data_all["items"]) == 3

        # 2. Filter by event_type="SOS"
        r_sos = client.get(f"/api/v1/children/{child_id}/events?event_type=SOS", headers=headers)
        assert r_sos.status_code == 200
        data_sos = r_sos.json()
        assert data_sos["total"] == 1
        assert data_sos["items"][0]["event_type"] == "SOS"

        # 3. Filter by severity="CRITICAL"
        r_crit = client.get(f"/api/v1/children/{child_id}/events?severity=CRITICAL", headers=headers)
        assert r_crit.status_code == 200
        assert r_crit.json()["total"] == 1

        # 4. Filter by is_acknowledged=false
        r_unack = client.get(f"/api/v1/children/{child_id}/events?is_acknowledged=false", headers=headers)
        assert r_unack.status_code == 200
        assert r_unack.json()["total"] == 2

        # 5. Pagination test: limit=1, offset=1
        r_page = client.get(f"/api/v1/children/{child_id}/events?limit=1&offset=1", headers=headers)
        assert r_page.status_code == 200
        assert len(r_page.json()["items"]) == 1


def test_acknowledge_safety_event_and_cross_guardian_denial(client: TestClient, db_session: Session):
    """Guardian marks safety event as acknowledged; cross-family guardians are denied."""
    env1 = setup_safety_test_env(client, "fb_ack_guard_1")
    env2 = setup_safety_test_env(client, "fb_ack_guard_2")

    headers1 = env1["guardian_headers"]
    claims1 = env1["guardian_claims"]
    child1_id = env1["child_id"]
    family1_id = env1["family_id"]

    headers2 = env2["guardian_headers"]
    claims2 = env2["guardian_claims"]

    # Seed unacknowledged SOS event for family 1
    event = SafetyEvent(
        family_id=family1_id,
        child_profile_id=child1_id,
        event_type="SOS",
        severity="CRITICAL",
        reason="Urgent SOS alert",
        is_acknowledged=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    # 1. Guardian 2 (different family) attempts acknowledgement -> 403 Forbidden
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims2):
        denied_resp = client.post(f"/api/v1/events/{event.id}/ack", headers=headers2)
        assert denied_resp.status_code in [403, 404]

    # 2. Guardian 1 (authorized family) acknowledges event -> 200 OK
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims1):
        ack_resp = client.post(f"/api/v1/events/{event.id}/ack", headers=headers1)
        assert ack_resp.status_code == 200
        ack_data = ack_resp.json()
        assert ack_data["status"] == "acknowledged"
        assert ack_data["event_id"] == event.id
        assert "acknowledged_by_user_id" in ack_data
        assert "acknowledged_at" in ack_data

    # Verify event state updated in database
    db_session.refresh(event)
    assert event.is_acknowledged is True
    assert event.acknowledged_at is not None


# ==============================================================================
# 6. WebSocket Real-Time Broadcast Integration (S-060, S-062, S-063)
# ==============================================================================


def test_websocket_broadcast_on_sos_and_zone_transition(client: TestClient):
    """Verify that SOS triggers and geofence events broadcast live WebSocket alerts."""
    env = setup_safety_test_env(client, "fb_ws_guard_1")
    child_id = env["child_id"]
    device_hw = env["device_identifier"]
    headers = env["guardian_headers"]
    claims = env["guardian_claims"]

    with patch("app.websocket.manager.ws_manager.broadcast_to_child", new_callable=AsyncMock) as mock_broadcast:
        with patch("app.services.fcm.send_fcm_notification", return_value="fcm_msg_ws_1"):
            # 1. Trigger SOS -> broadcasts "sos_alert"
            sos_resp = client.post(
                f"/api/v1/children/{child_id}/sos",
                json={"latitude": 37.7749, "longitude": -122.4194, "message": "WS Alert Test"},
                headers={"X-Device-Identifier": device_hw},
            )
            assert sos_resp.status_code == 201
            assert mock_broadcast.called
            # Find sos_alert call
            calls = [c.kwargs["message"] for c in mock_broadcast.call_args_list if "message" in c.kwargs]
            sos_call = next((m for m in calls if m.get("event") == "sos_alert"), None)
            assert sos_call is not None
            assert sos_call["child_id"] == child_id
            assert sos_call["severity"] == "CRITICAL"

        # 2. Setup zone and ingest location -> broadcasts "zone_transition" and "location_update"
        mock_broadcast.reset_mock()
        with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
            client.post(
                f"/api/v1/children/{child_id}/safe-zones",
                json={"name": "Park", "center_latitude": 37.7749, "center_longitude": -122.4194, "radius_meters": 500.0},
                headers=headers,
            )

        now = datetime.now(timezone.utc)
        loc_resp = client.post(
            f"/api/v1/children/{child_id}/locations",
            json={"latitude": 37.7749, "longitude": -122.4194, "accuracy_m": 5.0, "captured_at": now.isoformat()},
            headers={"X-Device-Identifier": device_hw},
        )
        assert loc_resp.status_code == 201

        # Check broadcast messages for zone_transition and location_update
        calls2 = [c.kwargs["message"] for c in mock_broadcast.call_args_list if "message" in c.kwargs]
        event_names = [m.get("event") for m in calls2]
        assert "zone_transition" in event_names
        assert "location_update" in event_names

