"""Game night router package"""

from .router import GameNightRouter

_router_instance = GameNightRouter()
router = _router_instance.router
