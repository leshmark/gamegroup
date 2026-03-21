"""Admin routes for user and system administration"""

from fastapi import APIRouter, HTTPException, Depends

from .models import UserUpsert
from database_service import DatabaseService
from auth_dependencies import AuthDependencies


class AdminRouter:
    def __init__(self):
        self.db_service = DatabaseService()
        self.auth_dependencies = AuthDependencies()
        self.router = self._build_router()

    def _build_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
        require_admin = self.auth_dependencies._get_require_admin_dependency()

        @router.get("/authorization")
        def get_authorizations(current_user: dict = Depends(require_admin)):
            """Get a list of all available authorizations/roles in the system (admin access required)"""
            return self._get_authorizations(current_user)

        @router.get("/user")
        def get_users(
            limit: int = 20,
            offset: int = 0,
            sort_by: str = "created_at",
            sort_order: str = "DESC",
            filter_criteria: str = None,
            current_user: dict = Depends(require_admin),
        ):
            """Get one or more users in the system (admin access required) with filtering and pagination"""
            return self._get_users(limit, offset, sort_by, sort_order, filter_criteria, current_user)

        @router.post("/user")
        def upsert_user(
            user: UserUpsert,
            current_user: dict = Depends(require_admin),
        ):
            """Upsert user information (admin access required)"""
            return self._upsert_user(user, current_user)

        @router.delete("/user/{username}")
        def delete_user(
            username: str,
            current_user: dict = Depends(require_admin),
        ):
            """Delete a user from the system by username (admin access required)"""
            return self._delete_user(username, current_user)

        return router

    def _get_authorizations(self, current_user: dict):
        return {"authorizations": ["is_viewer", "is_contributor", "is_admin"]}

    def _get_users(self, limit, offset, sort_by, sort_order, filter_criteria, current_user):
        try:
            users = self.db_service.read_table(
                table_name="users",
                filter_criteria=filter_criteria,
                columns=None,
                sort_by=sort_by,
                sort_order=sort_order.upper(),
                limit=limit,
                offset=offset,
            )
            count = self.db_service.read_table(
                table_name="users", filter_criteria=filter_criteria, count_only=True
            )
            return {"users": users, "count": count}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve users: {str(e)}"
            )

    def _upsert_user(self, user: UserUpsert, current_user: dict):
        try:
            authorizations = []
            if user.is_viewer:
                authorizations.append("is_viewer")
            if user.is_contributor:
                authorizations.append("is_contributor")
            if user.is_admin:
                authorizations.append("is_admin")

            authorizations_str = ",".join(authorizations) if authorizations else ""

            record = (
                {"username": user.username},
                {
                    "email": user.email,
                    "authorizations": authorizations_str,
                },
            )

            successful_ids, errors = self.db_service.upsert_records("users", [record])

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

    def _delete_user(self, username: str, current_user: dict):
        try:
            successful_ids, errors = self.db_service.delete_records("users", [{"username": username}])

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


_handler = AdminRouter()
router = _handler.router
