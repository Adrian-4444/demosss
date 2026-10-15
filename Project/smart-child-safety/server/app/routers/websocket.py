"""Authenticated WebSocket router for real-time guardian subscriptions and live telemetry streaming."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.child import ChildProfile
from app.models.user import FamilyMembership, UserProfile
from app.services import firebase_auth
from app.websocket.manager import ws_manager

logger = logging.getLogger("app.routers.websocket")

router = APIRouter(tags=["WebSockets"])


def verify_ws_token(token: Optional[str]) -> Optional[str]:
    """Verify Firebase ID token and return user ID, or None if invalid."""
    if not token or not token.strip():
        return None

    try:
        decoded_token = firebase_auth.verify_firebase_id_token(token.strip())
        uid = decoded_token.get("uid")
        if not uid:
            return None

        with SessionLocal() as db:
            user = db.query(UserProfile).filter(UserProfile.firebase_uid == uid).first()
            if not user or not user.is_active or user.disabled_at is not None:
                return None
            return user.id
    except Exception as exc:
        logger.warning("WebSocket token verification failed: %s", exc)
        return None


def is_user_authorized_for_child(user_id: str, child_id: str) -> bool:
    """Verify in database that the user is an active member of the family owning this child."""
    with SessionLocal() as db:
        child = db.query(ChildProfile).filter(ChildProfile.id == child_id).first()
        if not child or child.deleted_at is not None:
            return False

        membership = (
            db.query(FamilyMembership)
            .filter(
                FamilyMembership.family_id == child.family_id,
                FamilyMembership.user_id == user_id,
            )
            .first()
        )
        return membership is not None


@router.websocket("/ws")
async def websocket_event_stream(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
):
    """Authenticated real-time WebSocket connection for guardians.
    
    Accepts authentication credentials either via query parameter `?token=<firebase_id_token>`
    or as the first message payload `{"action": "authenticate", "token": "..."}`.
    
    Allows authorized guardians to subscribe to real-time events for children in their family.
    """
    user_id = verify_ws_token(token)

    # If token was not provided in query param, accept and wait for authentication message
    if not user_id:
        await websocket.accept()
        try:
            auth_msg = await websocket.receive_text()
            data = json.loads(auth_msg)
            if data.get("action") == "authenticate":
                user_id = verify_ws_token(data.get("token"))

            if not user_id:
                logger.warning("WebSocket client failed authentication; closing connection")
                await websocket.send_json({"event": "error", "detail": "Authentication failed"})
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        except Exception as exc:
            logger.warning("Error reading WebSocket auth handshake: %s", exc)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    else:
        await ws_manager.connect(websocket, user_id)

    # If connection was already accepted in handshake, register now
    if websocket not in ws_manager._active_connections:
        async with ws_manager._lock:
            ws_manager._active_connections[websocket] = user_id

    await ws_manager.send_personal_message(
        websocket,
        {
            "event": "connected",
            "status": "authenticated",
            "user_id": user_id,
        },
    )

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                msg = json.loads(raw_text)
            except json.JSONDecodeError:
                await ws_manager.send_personal_message(
                    websocket,
                    {"event": "error", "detail": "Malformed JSON payload"},
                )
                continue

            action = msg.get("action")

            if action == "subscribe":
                child_id = msg.get("child_id")
                if not child_id:
                    await ws_manager.send_personal_message(
                        websocket,
                        {"event": "error", "detail": "Missing child_id in subscription request"},
                    )
                    continue

                # S-055 Enforce per-child relationship authorization
                if is_user_authorized_for_child(user_id=user_id, child_id=child_id):
                    await ws_manager.subscribe(websocket, child_id)
                    await ws_manager.send_personal_message(
                        websocket,
                        {
                            "event": "subscribed",
                            "child_id": child_id,
                            "status": "ok",
                        },
                    )
                else:
                    logger.warning("Unauthorized WebSocket subscription attempt: user=%s, child=%s", user_id, child_id)
                    await ws_manager.send_personal_message(
                        websocket,
                        {
                            "event": "error",
                            "child_id": child_id,
                            "detail": "Unauthorized subscription: access denied for this child profile",
                        },
                    )

            elif action == "unsubscribe":
                child_id = msg.get("child_id")
                if child_id:
                    await ws_manager.unsubscribe(websocket, child_id)
                    await ws_manager.send_personal_message(
                        websocket,
                        {
                            "event": "unsubscribed",
                            "child_id": child_id,
                        },
                    )

            elif action == "ping":
                await ws_manager.send_personal_message(
                    websocket,
                    {"event": "pong"},
                )

            else:
                await ws_manager.send_personal_message(
                    websocket,
                    {"event": "error", "detail": f"Unknown action: '{action}'"},
                )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected normally")
    except Exception as exc:
        logger.warning("WebSocket connection encountered exception: %s", exc)
    finally:
        await ws_manager.disconnect(websocket)
