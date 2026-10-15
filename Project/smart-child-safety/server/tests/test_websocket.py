"""Automated test suite for Authenticated WebSockets, per-child subscriptions, and real-time event broadcasting."""

import asyncio
from unittest.mock import patch
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.orm import Session

from app.services.rate_limiter import (
    location_upload_limiter,
    pairing_claim_limiter,
    pairing_create_limiter,
)
from app.websocket.manager import ws_manager


@pytest.fixture(autouse=True)
def reset_limiters_and_ws():
    """Reset rate limiter histories and WebSocket manager state before each test run."""
    location_upload_limiter.reset()
    pairing_claim_limiter.reset()
    pairing_create_limiter.reset()
    # Reset in-memory WebSocket connections
    ws_manager._active_connections.clear()
    ws_manager._subscriptions.clear()


def setup_ws_environment(client: TestClient, db: Session, uid: str = "fb_ws_guardian_1"):
    """Helper to set up guardian, family, child profile, and paired device."""
    claims = {"uid": uid, "email": f"{uid}@test.com"}
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=claims):
        headers = {"Authorization": f"Bearer token_{uid}"}

        # 1. Create family
        fam_resp = client.post("/api/v1/families", json={"name": "WS Test Family"}, headers=headers)
        assert fam_resp.status_code == 201
        family_id = fam_resp.json()["family_id"]

        # 2. Create child profile
        child_resp = client.post(
            f"/api/v1/families/{family_id}/children",
            json={"first_name": "Oliver", "display_name": "Oliver Test"},
            headers=headers,
        )
        assert child_resp.status_code == 201
        child_id = child_resp.json()["id"]

        # 3. Create paired device
        device_identifier = f"test-ws-hw-{uid}"
        pair_resp = client.post("/api/v1/pairing/create", json={"child_profile_id": child_id}, headers=headers)
        assert pair_resp.status_code == 201
        raw_code = pair_resp.json()["pairing_code"]

        claim_resp = client.post(
            "/api/v1/pairing/claim",
            json={
                "pairing_code": raw_code,
                "device_identifier": device_identifier,
                "device_model": "Pixel 8",
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
# 1. WebSocket Authentication Handshake Tests (S-055)
# ==============================================================================

def test_websocket_connect_with_query_token_success(client: TestClient, db_session: Session):
    """Client can authenticate upon connection via ?token=<token> query parameter."""
    setup = setup_ws_environment(client, db_session, "fb_ws_query_token")

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        with client.websocket_connect("/api/v1/ws?token=valid_token") as ws:
            msg = ws.receive_json()
            assert msg["event"] == "connected"
            assert msg["status"] == "authenticated"
            assert "user_id" in msg


def test_websocket_connect_with_message_handshake_success(client: TestClient, db_session: Session):
    """Client connecting without query token can authenticate via first handshake message."""
    setup = setup_ws_environment(client, db_session, "fb_ws_msg_token")

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        with client.websocket_connect("/api/v1/ws") as ws:
            # Send auth message
            ws.send_json({"action": "authenticate", "token": "valid_token_handshake"})
            msg = ws.receive_json()
            assert msg["event"] == "connected"
            assert msg["status"] == "authenticated"


def test_websocket_unauthenticated_connection_rejected(client: TestClient):
    """Connecting with an invalid token causes the connection to close with policy violation (1008)."""
    with patch("app.services.firebase_auth.verify_firebase_id_token", side_effect=Exception("Invalid token")):
        with client.websocket_connect("/api/v1/ws") as ws:
            ws.send_json({"action": "authenticate", "token": "bogus_token"})
            msg = ws.receive_json()
            assert msg["event"] == "error"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


# ==============================================================================
# 2. Per-Child Subscription Authorization Tests (S-055)
# ==============================================================================

def test_websocket_subscribe_authorized_child(client: TestClient, db_session: Session):
    """Authorized guardian can subscribe to real-time events for their linked child."""
    setup = setup_ws_environment(client, db_session, "fb_ws_sub_auth")
    child_id = setup["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        with client.websocket_connect("/api/v1/ws?token=valid_token") as ws:
            ws.receive_json()  # Consume 'connected'

            # Subscribe to child
            ws.send_json({"action": "subscribe", "child_id": child_id})
            sub_resp = ws.receive_json()
            assert sub_resp["event"] == "subscribed"
            assert sub_resp["child_id"] == child_id
            assert sub_resp["status"] == "ok"


def test_websocket_subscribe_unauthorized_child_denied(client: TestClient, db_session: Session):
    """Guardian attempting to subscribe to an unlinked child receives an error response."""
    setup_a = setup_ws_environment(client, db_session, "fb_ws_sub_a")
    setup_b = setup_ws_environment(client, db_session, "fb_ws_sub_b")

    # Guardian B attempts to subscribe to Guardian A's child
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup_b["guardian_claims"]):
        with client.websocket_connect("/api/v1/ws?token=token_b") as ws:
            ws.receive_json()  # Consume 'connected'

            ws.send_json({"action": "subscribe", "child_id": setup_a["child_id"]})
            err_resp = ws.receive_json()
            assert err_resp["event"] == "error"
            assert "Unauthorized subscription" in err_resp["detail"]


def test_websocket_ping_pong_and_unsubscribe(client: TestClient, db_session: Session):
    """WebSocket responds to ping/pong and allows clean unsubscription."""
    setup = setup_ws_environment(client, db_session, "fb_ws_ping")
    child_id = setup["child_id"]

    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        with client.websocket_connect("/api/v1/ws?token=valid_token") as ws:
            ws.receive_json()  # Consume 'connected'

            # Ping
            ws.send_json({"action": "ping"})
            assert ws.receive_json()["event"] == "pong"

            # Subscribe then unsubscribe
            ws.send_json({"action": "subscribe", "child_id": child_id})
            assert ws.receive_json()["event"] == "subscribed"

            ws.send_json({"action": "unsubscribe", "child_id": child_id})
            assert ws.receive_json()["event"] == "unsubscribed"


# ==============================================================================
# 3. Real-Time Broadcast Integration Tests (S-055, S-052)
# ==============================================================================

def test_websocket_broadcast_on_command_ack(client: TestClient, db_session: Session):
    """When child device acknowledges a command via REST, subscribed guardian receives real-time broadcast."""
    setup = setup_ws_environment(client, db_session, "fb_ws_broadcast")
    child_id = setup["child_id"]
    headers_device = {"X-Device-Identifier": setup["device_identifier"]}

    # Create command
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        cmd_resp = client.post(
            f"/api/v1/children/{child_id}/commands",
            json={"command_type": "SAFETY_CHECK", "expiry_seconds": 300},
            headers=setup["guardian_headers"],
        )
        command_id = cmd_resp.json()["id"]

    # Guardian opens WebSocket connection and subscribes to child
    with patch("app.services.firebase_auth.verify_firebase_id_token", return_value=setup["guardian_claims"]):
        with client.websocket_connect("/api/v1/ws?token=valid_token") as ws:
            ws.receive_json()  # Connected

            ws.send_json({"action": "subscribe", "child_id": child_id})
            assert ws.receive_json()["event"] == "subscribed"

            # Now child device acknowledges command via REST endpoint
            ack_resp = client.post(
                f"/api/v1/commands/{command_id}/ack",
                json={"status": "EXECUTED", "execution_result": "I am safe and sound"},
                headers=headers_device,
            )
            assert ack_resp.status_code == 200

            # Subscribed guardian receives real-time broadcast message over WebSocket!
            broadcast_event = ws.receive_json()
            assert broadcast_event["event"] == "command_status_changed"
            assert broadcast_event["child_id"] == child_id
            assert broadcast_event["command_id"] == command_id
            assert broadcast_event["status"] == "EXECUTED"
            assert broadcast_event["execution_result"] == "I am safe and sound"
