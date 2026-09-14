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

        @router.get("/vote-history")
        def get_vote_history(current_user: dict = Depends(require_admin)):
            """Return each game's next-play vote counts for the last 12 calendar weeks."""
            return self._get_vote_history(current_user)

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
            try:
                parsed_filter = DatabaseService.parse_http_filter_criteria(filter_criteria) if filter_criteria else None
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            return self._get_users(limit, offset, sort_by, sort_order, parsed_filter, current_user)

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
        return {"authorizations": ["is_viewer", "is_contributor", "is_admin"]}  # available authorization levels

    def _get_vote_history(self, current_user: dict):
        try:
            conn = self.db_service.get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        WITH weeks AS (
                            SELECT generate_series(
                                date_trunc('week', CURRENT_DATE) - INTERVAL '11 weeks',
                                date_trunc('week', CURRENT_DATE),
                                INTERVAL '1 week'
                            )::date AS week_start
                        ),
                        weekly_votes AS (
                            SELECT
                                game_id,
                                date_trunc('week', created_at)::date AS week_start,
                                COUNT(*) AS vote_count
                            FROM game_votes
                            WHERE created_at >= date_trunc('week', CURRENT_DATE) - INTERVAL '11 weeks'
                            GROUP BY game_id, date_trunc('week', created_at)::date
                        )
                        SELECT
                            game.id,
                            game.title,
                            json_agg(
                                json_build_object(
                                    'week_start', weeks.week_start,
                                    'vote_count', COALESCE(weekly_votes.vote_count, 0)
                                )
                                ORDER BY weeks.week_start
                            ) AS weekly_votes
                        FROM games AS game
                        CROSS JOIN weeks
                        LEFT JOIN weekly_votes
                            ON weekly_votes.game_id = game.id
                            AND weekly_votes.week_start = weeks.week_start
                        GROUP BY game.id, game.title
                        ORDER BY LOWER(game.title), game.id
                        """
                    )
                    rows = cursor.fetchall()
            finally:
                conn.close()

            games = [
                {"game_id": game_id, "title": title, "weekly_votes": weekly_votes}
                for game_id, title, weekly_votes in rows
            ]
            weeks = games[0]["weekly_votes"] if games else []
            return {
                "weeks": [week["week_start"] for week in weeks],
                "games": games,
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve vote history: {str(e)}"
            )

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
