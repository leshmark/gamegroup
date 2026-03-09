"""Tag routes for game tag management"""

from fastapi import APIRouter, Depends
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auth_dependencies import AuthDependencies

router = APIRouter(prefix="/api/v1/tag", tags=["tag"])


def setup_tag_routes(auth_dependencies: "AuthDependencies"):
    """Configure tag routes with service dependencies"""

    @router.get("")
    def get_tags():
        """Retrieve the list of predefined tags"""
        # TODO: Implement tag retrieval
        pass

    @router.post("")
    def add_tag(
        tag_name: str,
        current_user: dict = Depends(
            auth_dependencies._get_require_contributor_dependency()
        ),
    ):
        """Add a new tag to the predefined list (contributor access required)"""
        # TODO: Implement tag addition with authorization check
        pass

    return router
