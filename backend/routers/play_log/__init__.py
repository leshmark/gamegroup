"""Play log router package"""

from .router import PlayLogRouter

_router_instance = PlayLogRouter()
router = _router_instance.router
