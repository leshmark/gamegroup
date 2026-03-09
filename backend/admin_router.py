"""Admin routes for user and system administration"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db_utils import DatabaseService
    from auth_dependencies import AuthDependencies
    from game_image_updater import GameImageUpdater

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class UserUpsert(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=1, max_length=255)
    is_viewer: bool = False
    is_contributor: bool = False
    is_admin: bool = False


def setup_admin_routes(
    db_service: "DatabaseService",
    auth_dependencies: "AuthDependencies",
    game_image_updater: "GameImageUpdater",
):
    """Configure admin routes with service dependencies"""

    @router.post("/action/update-game-images")
    def update_game_images(
        current_user: dict = Depends(auth_dependencies._get_require_admin_dependency()),
    ):
        """Update missing game image URLs from BoardGameGeek (admin access required)"""
        try:
            return game_image_updater.update_missing_images()
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to update game images: {str(e)}"
            )

    @router.get("/authorization")
    def get_authorizations(
        current_user: dict = Depends(auth_dependencies._get_require_admin_dependency()),
    ):
        """Get a list of all available authorizations/roles in the system (admin access required)"""
        return {"authorizations": ["is_viewer", "is_contributor", "is_admin"]}

    @router.get("/user")
    def get_users(
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "DESC",
        filter_criteria: str = None,
        current_user: dict = Depends(auth_dependencies._get_require_admin_dependency()),
    ):
        """Get one or more users in the system (admin access required) with filtering and pagination"""
        try:
            users = db_service.read_table(
                table_name="users",
                filter_criteria=filter_criteria,
                columns=None,
                sort_by=sort_by,
                sort_order=sort_order.upper(),
                limit=limit,
                offset=offset,
            )
            count = db_service.read_table(
                table_name="users", filter_criteria=filter_criteria, count_only=True
            )
            return {"users": users, "count": count}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve users: {str(e)}"
            )

    @router.post("/user")
    def upsert_user(
        user: UserUpsert,
        current_user: dict = Depends(auth_dependencies._get_require_admin_dependency()),
    ):
        """Upsert user information (admin access required)"""
        try:
            # Build authorizations string from boolean fields
            authorizations = []
            if user.is_viewer:
                authorizations.append("is_viewer")
            if user.is_contributor:
                authorizations.append("is_contributor")
            if user.is_admin:
                authorizations.append("is_admin")
            
            authorizations_str = ",".join(authorizations) if authorizations else ""
            
            # Use upsert_records to add or update the user
            # Key field is email, update fields are username and authorizations
            record = (
                {"username": user.username},  # Key field to find existing user
                {
                    "email": user.email,
                    "authorizations": authorizations_str,
                },
            )
            
            successful_ids, errors = db_service.upsert_records("users", [record])
            
            if errors:
                raise HTTPException(
                    status_code=500, detail=f"Failed to upsert user: {errors[0]['error']}"
                )
            
            user_id = successful_ids[0]
            return {
                "message": "User upserted successfully",
                "user_id": user_id,
                "email": user.email,
                "username": user.username,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upsert user: {str(e)}")

    @router.delete("/user/{username}")
    def delete_user(
        username: str,
        current_user: dict = Depends(auth_dependencies._get_require_admin_dependency()),
    ):
        """Delete a user from the system by username (admin access required)"""
        try:
            # Use delete_records to delete the user by username
            successful_ids, errors = db_service.delete_records("users", [{"username": username}])

            if errors:
                error_detail = errors[0]["error"]
                if "No record found" in error_detail:
                    raise HTTPException(status_code=404, detail=f"User with username '{username}' not found")
                else:
                    raise HTTPException(status_code=500, detail=f"Failed to delete user: {error_detail}")

            deleted_id = successful_ids[0]
            return {"message": f"User '{username}' deleted successfully", "username": username, "user_id": deleted_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")

    return router
