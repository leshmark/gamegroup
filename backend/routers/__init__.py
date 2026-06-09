"""Routers package for API endpoints"""

from .admin import router as admin_router
from .auth import router as auth_router
from .game import router as game_router
from .game_night import router as game_night_router

__all__ = [
    "admin_router",
    "auth_router",
    "game_router",
    "game_night_router",
]
