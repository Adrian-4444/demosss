"""WebSocket package exporting the connection manager."""

from app.websocket.manager import WebSocketConnectionManager, ws_manager

__all__ = ["WebSocketConnectionManager", "ws_manager"]
