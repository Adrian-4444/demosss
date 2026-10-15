"""Automated tests for Firebase authentication, profile management, and relationship authorization."""

from unittest.mock import patch
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import UserProfile, Family, FamilyMembership
from app.models.child import ChildProfile


def test_unauthenticated_request_returns_401(client: TestClient):
    """Protected endpoints require Authorization Bearer header."""
    response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_invalid_bearer_token_returns_401(client: TestClient):
    """Invalid or unverified token returns 401 Unauthorized."""
    with patch("app.services.firebase_auth.auth.verify_id_token", side_effect=Exception("Invalid signature")):
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer bad-token-123"})
        assert response.status_code == 401


def test_authenticated_profile_auto_provisioning(client: TestClient, db_session: Session):
    """First-time authenticated user is automatically provisioned in database."""
    mock_claims = {
        "uid": "fb_mock_uid_new_1",
        "email": "newuser@example.com",
        "name": "New User",
    }

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=mock_claims):
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer valid-mock-token"})
        assert response.status_code == 200
        data = response.json()
        assert data["profile"]["firebase_uid"] == "fb_mock_uid_new_1"
        assert data["profile"]["email"] == "newuser@example.com"
        assert data["profile"]["display_name"] == "New User"
        assert data["families"] == []
        assert data["children"] == []

        # Verify persisted in database
        persisted = db_session.query(UserProfile).filter_by(firebase_uid="fb_mock_uid_new_1").first()
        assert persisted is not None
        assert persisted.email == "newuser@example.com"


def test_update_profile(client: TestClient, db_session: Session):
    """User can update permitted profile fields."""
    mock_claims = {
        "uid": "fb_mock_update_user",
        "email": "updateuser@example.com",
        "name": "Original Name",
    }

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=mock_claims):
        # First call to provision
        client.get("/api/v1/me", headers={"Authorization": "Bearer valid-token"})

        # Update profile
        update_payload = {"display_name": "Updated Name", "phone_number": "+1234567890"}
        response = client.patch(
            "/api/v1/me",
            json=update_payload,
            headers={"Authorization": "Bearer valid-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"
        assert data["phone_number"] == "+1234567890"


def test_create_family_and_child_profile(client: TestClient):
    """Guardian creates family and registers child profile."""
    mock_claims = {
        "uid": "fb_guardian_fam_test",
        "email": "fam_guardian@example.com",
        "name": "Family Guardian",
    }

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=mock_claims):
        headers = {"Authorization": "Bearer token-guardian"}

        # 1. Create family
        fam_resp = client.post("/api/v1/families", json={"name": "Johnson Family"}, headers=headers)
        assert fam_resp.status_code == 201
        fam_data = fam_resp.json()
        family_id = fam_data["family_id"]
        assert fam_data["role"] == "owner"

        # 2. Create child profile in family
        child_payload = {
            "first_name": "Bobby",
            "last_name": "Johnson",
            "display_name": "Bobby Johnson",
            "gender": "male",
            "sharing_enabled": True,
        }
        child_resp = client.post(
            f"/api/v1/families/{family_id}/children",
            json=child_payload,
            headers=headers,
        )
        assert child_resp.status_code == 201
        child_data = child_resp.json()
        assert child_data["first_name"] == "Bobby"
        assert child_data["family_id"] == family_id

        # 3. Verify /api/v1/me lists the family and child
        me_resp = client.get("/api/v1/me", headers=headers)
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert len(me_data["families"]) == 1
        assert len(me_data["children"]) == 1
        assert me_data["children"][0]["first_name"] == "Bobby"


def test_cross_family_access_denied(client: TestClient, db_session: Session):
    """Guardian from Family B cannot create a child or access resources under Family A."""
    # Guardian A setup
    claims_a = {"uid": "fb_user_a", "email": "userA@example.com", "name": "User A"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims_a):
        resp_a = client.post("/api/v1/families", json={"name": "Family A"}, headers={"Authorization": "Bearer token_a"})
        family_a_id = resp_a.json()["family_id"]

    # Guardian B attempts to create child in Family A
    claims_b = {"uid": "fb_user_b", "email": "userB@example.com", "name": "User B"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims_b):
        resp_b = client.post(
            f"/api/v1/families/{family_a_id}/children",
            json={"first_name": "IntruderChild", "display_name": "Intruder"},
            headers={"Authorization": "Bearer token_b"},
        )
        assert resp_b.status_code == 403
        assert "Access denied" in resp_b.json()["detail"]


def test_deactivated_user_blocked(client: TestClient, db_session: Session):
    """Deactivated user account receives 403 Forbidden."""
    claims = {"uid": "fb_deactivated_user", "email": "deactivated@example.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        # Auto-provision
        client.get("/api/v1/me", headers={"Authorization": "Bearer token"})

        # Deactivate user in database
        user = db_session.query(UserProfile).filter_by(firebase_uid="fb_deactivated_user").first()
        user.is_active = False
        db_session.commit()

        # Subsequent call must be blocked
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer token"})
        assert response.status_code == 403
        assert "deactivated" in response.json()["detail"].lower()
