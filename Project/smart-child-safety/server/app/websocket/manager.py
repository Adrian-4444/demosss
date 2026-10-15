"""WebSocket connection and subscription manager for real-time guardian telemetry and events."""

import asyncio
import logging
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("app.websocket.manager")


class WebSocketConnectionManager:
    """Manages active WebSocket sessions and per-child authorized event distribution."""

    def __init__(self):
        # Maps active WebSocket instance -> authenticated user_id
        self._active_connections: Dict[WebSocket, str] = {}
        # Maps child_id -> set of subscribed WebSocket instances
        self._subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    @property
    def active_connections_count(self) -> int:
        """Total number of currently connected WebSocket clients."""
        return len(self._active_connections)

    def subscriptions_count_for_child(self, child_id: str) -> int:
        """Number of active subscriptions for a specific child."""
        return len(self._subscriptions.get(child_id, set()))

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept incoming WebSocket connection and register authenticated caller."""
        await websocket.accept()
        async with self._lock:
            self._active_connections[websocket] = user_id
        logger.info("WebSocket connected for user_id=%s (active=%d)", user_id, len(self._active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister closed WebSocket connection and clean up all subscriptions."""
        async with self._lock:
            user_id = self._active_connections.pop(websocket, "unknown")
            # Remove from all child subscription sets
            for child_id, subs in list(self._subscriptions.items()):
                subs.discard(websocket)
                if not subs:
                    self._subscriptions.pop(child_id, None)

        logger.info("WebSocket disconnected for user_id=%s (active=%d)", user_id, len(self._active_connections))

    async def subscribe(self, websocket: WebSocket, child_id: str) -> None:
        """Add connection to child event subscription list."""
        async with self._lock:
            if websocket in self._active_connections:
                self._subscriptions[child_id].add(websocket)
                logger.debug("User %s subscribed to child_id=%s", self._active_connections[websocket], child_id)

    async def unsubscribe(self, websocket: WebSocket, child_id: str) -> None:
        """Remove connection from child event subscription list."""
        async with self._lock:
            if child_id in self._subscriptions:
                self._subscriptions[child_id].discard(websocket)
                if not self._subscriptions[child_id]:
                    del self._subscriptions[child_id]

    async def send_personal_message(self, websocket: WebSocket, message: dict) -> None:
        """Send direct JSON message to a single connected client."""
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.warning("Failed to send personal WebSocket message: %s", exc)

    async def broadcast_to_child(self, child_id: str, message: dict) -> int:
        """Broadcast an event payload to all authenticated guardians subscribed to this child.
        
        Returns the number of subscribers successfully messaged.
        """
        async with self._lock:
            subscribers = list(self._subscriptions.get(child_id, set()))

        if not subscribers:
            logger.debug("No active subscribers for child_id=%s; event not broadcast", child_id)
            return 0

        delivery_count = 0
        dead_connections = []

        for ws in subscribers:
            try:
                await ws.send_json(message)
                delivery_count += 1
            except Exception as exc:
                logger.warning("Failed delivering event to subscriber: %s; scheduling cleanup", exc)
                dead_connections.append(ws)

        if dead_connections:
            for dead_ws in dead_connections:
                await self.disconnect(dead_ws)

        logger.info(
            "Broadcast event '%s' for child_id=%s to %d subscribers",
            message.get("event", "unknown"),
            child_id,
            delivery_count,
        )
        return delivery_count

    async def reset(self) -> None:
        """Reset all connections and subscriptions (used for clean testing)."""
        async with self._lock:
            self._active_connections.clear()
            self._subscriptions.clear()


# Global WebSocket manager singleton
ws_manager = WebSocketConnectionManager()
