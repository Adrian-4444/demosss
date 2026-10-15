"""API Routers package exporting health, user, pairing, location, command, and websocket routers."""

from app.routers.command import router as command_router
from app.routers.health import router as health_router
from app.routers.location import router as location_router
from app.routers.maintenance import router as maintenance_router
from app.routers.pairing import router as pairing_router
from app.routers.safety import router as safety_router
from app.routers.user import family_router, router as user_router
from app.routers.websocket import router as websocket_router

__all__ = [
    "health_router",
    "user_router",
    "family_router",
    "pairing_router",
    "location_router",
    "command_router",
    "safety_router",
    "maintenance_router",
    "websocket_router",
]


