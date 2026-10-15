"""FCM (Firebase Cloud Messaging) Adapter service for downstream device push signaling."""

import logging
from typing import Dict, Optional

import firebase_admin
from firebase_admin import messaging

from app.services.firebase_auth import initialize_firebase

logger = logging.getLogger("app.services.fcm")


def send_fcm_command_signal(
    target_token: str,
    child_id: str,
    command_id: str,
    command_type: str,
) -> Optional[str]:
    """Send a lightweight, privacy-safe data push signal instructing the child app to sync pending commands.
    
    In accordance with privacy requirements, sensitive command payloads and location details are NEVER
    sent through third-party push notification channels. The FCM payload is strictly a wakeup signal.
    
    Returns the FCM message ID on success, or None if the send failed. Never raises exceptions.
    """
    if not target_token or not target_token.strip():
        logger.debug("No FCM token available for child_id=%s, skipping push signal", child_id)
        return None

    try:
        initialize_firebase()
    except Exception as exc:
        logger.warning("Firebase not available for FCM push: %s", exc)
        return None

    try:
        # Minimal data-only message (high priority for prompt wakeup)
        message = messaging.Message(
            data={
                "action": "SYNC_PENDING_COMMANDS",
                "child_id": str(child_id),
                "command_id": str(command_id),
                "command_type": str(command_type),
            },
            token=target_token.strip(),
            android=messaging.AndroidConfig(
                priority="high",
                ttl=300,  # 5 minutes TTL
            ),
        )

        message_id = messaging.send(message)
        logger.info(
            "Successfully sent FCM command signal command_id=%s to child_id=%s (message_id=%s)",
            command_id,
            child_id,
            message_id,
        )
        return message_id
    except messaging.UnregisteredError:
        logger.warning(
            "FCM token is unregistered/stale for child_id=%s; token should be refreshed",
            child_id,
        )
        return None
    except Exception as exc:
        logger.warning(
            "FCM push signal failed for command_id=%s (error=%s). Command remains persisted in database.",
            command_id,
            type(exc).__name__,
        )
        return None


def send_fcm_notification(
    target_token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Send a high-priority push notification (e.g. for SOS alerts or geofence breaches).
    
    Returns the FCM message ID on success, or None on failure. Never raises exceptions.
    """
    if not target_token or not target_token.strip():
        return None

    try:
        initialize_firebase()
    except Exception as exc:
        logger.warning("Firebase not available for FCM push: %s", exc)
        return None

    try:
        string_data = {k: str(v) for k, v in (data or {}).items()}
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=string_data,
            token=target_token.strip(),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    priority="max",
                    channel_id="child_safety_alerts",
                ),
            ),
        )

        message_id = messaging.send(message)
        logger.info("Sent FCM alert notification (message_id=%s)", message_id)
        return message_id
    except Exception as exc:
        logger.warning("Failed to send FCM notification: %s", exc)
        return None
