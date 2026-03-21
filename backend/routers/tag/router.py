"""Tag routes for game tag management"""

from fastapi import APIRouter, Depends

from auth_dependencies import AuthDependencies


class TagRouter:
    def __init__(self):
        self.auth_dependencies = AuthDependencies()
        self.router = self._build_router()

    def _build_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1/tag", tags=["tag"])
        require_contributor = self.auth_dependencies._get_require_contributor_dependency()

        @router.get("")
        def get_tags():
            """Retrieve the list of predefined tags"""
            return self._get_tags()

        @router.post("")
        def add_tag(
            tag_name: str,
            current_user: dict = Depends(require_contributor),
        ):
            """Add a new tag to the predefined list (contributor access required)"""
            return self._add_tag(tag_name, current_user)

        return router

    def _get_tags(self):
        # TODO: Implement tag retrieval
        pass

    def _add_tag(self, tag_name: str, current_user: dict):
        # TODO: Implement tag addition with authorization check
        pass


_handler = TagRouter()
router = _handler.router
