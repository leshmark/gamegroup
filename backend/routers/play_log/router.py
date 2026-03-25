"""Play log routes for recording and retrieving game play sessions"""

from fastapi import APIRouter, HTTPException, Depends
import logging

from .models import PlayLogSessionCreate
from database_service import DatabaseService
from auth_dependencies import AuthDependencies

logger = logging.getLogger(__name__)


class PlayLogRouter:
    def __init__(self):
        self.db_service = DatabaseService()
        self.auth_dependencies = AuthDependencies()
        self.router = self._build_router()

    def _build_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1/play-log", tags=["play-log"])
        require_viewer = self.auth_dependencies._get_require_viewer_dependency()
        require_contributor = self.auth_dependencies._get_require_contributor_dependency()
        require_admin = self.auth_dependencies._get_require_admin_dependency()

        @router.get("")
        def get_play_log_sessions(
            limit: int = 10,
            offset: int = 0,
            current_user: dict = Depends(require_viewer),
        ):
            """Retrieve paginated play log sessions in reverse chronological order (viewer access required)"""
            return self._get_play_log_sessions(limit, offset, current_user)

        @router.post("")
        def create_play_log_session(
            session: PlayLogSessionCreate,
            current_user: dict = Depends(require_contributor),
        ):
            """Create a new play log session entry (contributor access required)"""
            return self._create_play_log_session(session, current_user)

        @router.get("/requested-games")
        def get_requested_games(
            limit: int = 5,
            current_user: dict = Depends(require_viewer),
        ):
            """Retrieve the top voted games for next play (viewer access required)"""
            return self._get_requested_games(limit, current_user)

        @router.delete("/{session_id}")
        def delete_play_log_session(
            session_id: int,
            current_user: dict = Depends(require_admin),
        ):
            """Delete a play log session (admin access required)"""
            return self._delete_play_log_session(session_id, current_user)

        return router

    def _get_play_log_sessions(self, limit: int, offset: int, current_user: dict):
        try:
            sessions = self.db_service.read_table(
                table_name="play_log_sessions",
                sort_by="session_date",
                sort_order="DESC",
                limit=limit,
                offset=offset,
            )
            total_count = self.db_service.read_table(
                table_name="play_log_sessions",
                count_only=True,
            )

            # Enrich each session with game titles for the games_played IDs
            enriched_sessions = []
            for session in sessions:
                enriched = dict(session)
                game_ids = session.get("games_played") or []
                if game_ids:
                    id_list = ",".join(str(gid) for gid in game_ids)
                    games = self.db_service.read_table(
                        table_name="games",
                        filter_criteria=f"id IN ({id_list})",
                        columns=["id", "title", "image_url"],
                    )
                    enriched["games_played_details"] = games
                else:
                    enriched["games_played_details"] = []
                enriched_sessions.append(enriched)

            return {
                "sessions": enriched_sessions,
                "total": total_count,
                "limit": limit,
                "offset": offset,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve play log sessions: {str(e)}")

    def _create_play_log_session(self, session: PlayLogSessionCreate, current_user: dict):
        try:
            key_fields = {}  # Always insert new sessions
            data_fields = session.model_dump(exclude_none=True)
            data_fields["logged_by"] = current_user["email"]

            successful_ids, errors = self.db_service.upsert_records(
                "play_log_sessions",
                [(key_fields, data_fields)],
            )

            if errors:
                raise HTTPException(status_code=500, detail=f"Failed to create play log session: {errors[0]['error']}")

            return {"message": "Play log session created successfully", "session_id": successful_ids[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create play log session: {str(e)}")

    def _get_requested_games(self, limit: int, current_user: dict):
        try:
            games = self.db_service.read_table(
                table_name="games",
                filter_criteria="next_play_vote_count > 0",
                columns=["id", "title", "bgg_rating", "short_description", "image_url", "next_play_vote_count"],
                sort_by="next_play_vote_count",
                sort_order="DESC",
                limit=limit,
            )
            return {"games": games}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve requested games: {str(e)}")

    def _delete_play_log_session(self, session_id: int, current_user: dict):
        try:
            conn = self.db_service.get_connection()
            try:
                from psycopg2 import sql
                with conn.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DELETE FROM play_log_sessions WHERE id = %s RETURNING id"),
                        [session_id],
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise HTTPException(status_code=404, detail=f"Play log session {session_id} not found")
                    conn.commit()
            finally:
                conn.close()
            return {"message": "Play log session deleted successfully", "session_id": session_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete play log session: {str(e)}")
