"""Routers package for API endpoints"""

from .admin import router as admin_router
from .auth import router as auth_router
from .game import router as game_router
from .play_log import router as play_log_router

__all__ = [
    "admin_router",
    "auth_router",
    "game_router",
    "play_log_router",
]
