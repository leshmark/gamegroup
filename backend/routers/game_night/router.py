"""Game night routes for recording and retrieving game play sessions"""

from fastapi import APIRouter, HTTPException, Depends
import logging
from collections import Counter
from datetime import datetime, timedelta

from .models import GameNightSessionCreate, GameNightCommentCreate
from database_service import DatabaseService
from auth_dependencies import AuthDependencies

logger = logging.getLogger(__name__)


class GameNightRouter:
    def __init__(self):
        self.db_service = DatabaseService()
        self.auth_dependencies = AuthDependencies()
        self.router = self._build_router()

    def _build_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1/game-night", tags=["game-night"])
        require_viewer = self.auth_dependencies._get_require_viewer_dependency()
        require_contributor = self.auth_dependencies._get_require_contributor_dependency()
        require_admin = self.auth_dependencies._get_require_admin_dependency()

        @router.get("")
        def get_game_night_sessions(
            limit: int = 10,
            offset: int = 0,
            filter_criteria: str = None,
            current_user: dict = Depends(require_viewer),
        ):
            """Retrieve paginated game night sessions in reverse chronological order (viewer access required)"""
            try:
                parsed_filter = DatabaseService.parse_http_filter_criteria(filter_criteria) if filter_criteria else None
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            return self._get_game_night_sessions(limit, offset, current_user, filter_criteria=parsed_filter)

        @router.post("")
        def create_game_night_session(
            session: GameNightSessionCreate,
            current_user: dict = Depends(require_contributor),
        ):
            """Create a new game night session entry (contributor access required)"""
            return self._create_game_night_session(session, current_user)

        @router.get("/requested-games")
        def get_requested_games(
            limit: int = 5,
            current_user: dict = Depends(require_viewer),
        ):
            """Retrieve the top voted games for next play (viewer access required)"""
            return self._get_requested_games(limit, current_user)

        @router.delete("/{session_id}")
        def delete_game_night_session(
            session_id: int,
            current_user: dict = Depends(require_admin),
        ):
            """Delete a game night session (admin access required)"""
            return self._delete_game_night_session(session_id, current_user)

        @router.get("/discussion")
        def get_discussion_comments(
            current_user: dict = Depends(require_viewer),
        ):
            """Retrieve recent discussion comments for the upcoming game night session (viewer access required)"""
            return self._get_discussion_comments(current_user)

        @router.post("/discussion")
        def post_discussion_comment(
            comment: GameNightCommentCreate,
            current_user: dict = Depends(require_viewer),
        ):
            """Post a comment to the upcoming game night discussion (viewer access required)"""
            return self._post_discussion_comment(comment, current_user)

        @router.delete("/discussion/{comment_id}")
        def delete_discussion_comment(
            comment_id: int,
            current_user: dict = Depends(require_admin),
        ):
            """Delete a discussion comment (admin access required)"""
            return self._delete_discussion_comment(comment_id, current_user)

        return router

    def _get_game_night_sessions(self, limit: int, offset: int, current_user: dict, filter_criteria: list = None):
        try:
            sessions = self.db_service.read_table(
                table_name="game_night_sessions",
                filter_criteria=filter_criteria,
                sort_by="session_date",
                sort_order="DESC",
                limit=limit,
                offset=offset,
            )
            total_count = self.db_service.read_table(
                table_name="game_night_sessions",
                filter_criteria=filter_criteria,
                count_only=True,
            )

            # Enrich each session with game titles for the games_played IDs
            enriched_sessions = []
            for session in sessions:
                enriched = dict(session)
                game_ids = session.get("games_played") or []
                if game_ids:
                    games = self.db_service.read_table(
                        table_name="games",
                        filter_criteria=[{"col": "id", "op": "IN", "val": game_ids}],
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
            raise HTTPException(status_code=500, detail=f"Failed to retrieve game night sessions: {str(e)}")

    def _create_game_night_session(self, session: GameNightSessionCreate, current_user: dict):
        try:
            key_fields = {}  # Always insert new sessions
            data_fields = session.model_dump(exclude_none=True)
            data_fields["logged_by"] = current_user["email"]

            successful_ids, errors = self.db_service.upsert_records(
                "game_night_sessions",
                [(key_fields, data_fields)],
            )

            if errors:
                raise HTTPException(status_code=500, detail=f"Failed to create game night session: {errors[0]['error']}")

            return {"message": "Game night session created successfully", "session_id": successful_ids[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create game night session: {str(e)}")

    def _get_requested_games(self, limit: int, current_user: dict):
        try:
            fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
            latest = self._get_game_night_sessions(limit=1, offset=0, current_user=current_user)
            sessions = latest.get("sessions", [])
            if sessions and sessions[0].get("session_date"):
                latest_session_date = sessions[0]["session_date"]
                if isinstance(latest_session_date, str):
                    latest_session_date = datetime.fromisoformat(latest_session_date)
                cutoff = max(fourteen_days_ago, latest_session_date)
            else:
                cutoff = fourteen_days_ago

            # Fetch all active votes within the 2-week window
            active_votes = self.db_service.read_table(
                table_name="game_votes",
                filter_criteria=[{"col": "created_at", "op": ">", "val": cutoff}],
                columns=["game_id"],
            )
            if not active_votes:
                return {"games": []}

            # Count votes per game and pick the top N game IDs
            vote_counts = Counter(v["game_id"] for v in active_votes)
            top_game_ids = [gid for gid, _ in vote_counts.most_common(limit)]

            # Fetch game details for those IDs
            games = self.db_service.read_table(
                table_name="games",
                filter_criteria=[{"col": "id", "op": "IN", "val": top_game_ids}],
                columns=["id", "title", "bgg_rating", "short_description", "image_url", "bgg_link", "min_players", "max_players"],
            )

            # Attach vote counts and return sorted by count descending
            game_map = {g["id"]: g for g in games}
            result = []
            for gid, count in vote_counts.most_common(limit):
                if gid in game_map:
                    game = dict(game_map[gid])
                    game["next_play_vote_count"] = count
                    result.append(game)

            return {"games": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve requested games: {str(e)}")

    def _delete_game_night_session(self, session_id: int, current_user: dict):
        try:
            conn = self.db_service.get_connection()
            try:
                from psycopg2 import sql
                with conn.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DELETE FROM game_night_sessions WHERE id = %s RETURNING id"),
                        [session_id],
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise HTTPException(status_code=404, detail=f"Game night session {session_id} not found")
                    conn.commit()
            finally:
                conn.close()
            return {"message": "Game night session deleted successfully", "session_id": session_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete game night session: {str(e)}")

    def _get_comment_cutoff(self, current_user: dict) -> datetime:
        """Return the cutoff datetime: max(14 days ago, last session date)."""
        fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
        latest = self._get_game_night_sessions(limit=1, offset=0, current_user=current_user)
        sessions = latest.get("sessions", [])
        if sessions and sessions[0].get("session_date"):
            latest_session_date = sessions[0]["session_date"]
            if isinstance(latest_session_date, str):
                latest_session_date = datetime.fromisoformat(latest_session_date)
            return max(fourteen_days_ago, latest_session_date)
        return fourteen_days_ago

    def _get_discussion_comments(self, current_user: dict):
        try:
            cutoff = self._get_comment_cutoff(current_user)
            comments = self.db_service.read_table(
                table_name="game_night_comments",
                filter_criteria=[{"col": "created_at", "op": ">", "val": cutoff}],
                sort_by="created_at",
                sort_order="ASC",
            )
            return {"comments": comments}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to retrieve discussion comments: {str(e)}")

    def _post_discussion_comment(self, comment: GameNightCommentCreate, current_user: dict):
        try:
            author_email = current_user["email"]
            username = current_user.get("username", "")
            is_guest = "gamegroupguest" in username.lower()

            if is_guest:
                display_name = (comment.contributor_name or "").strip() or "Anonymous Coward"
            else:
                display_name = username or author_email

            data_fields = {
                "comment_text": comment.comment_text.strip(),
                "author_email": author_email,
                "display_name": display_name,
            }

            successful_ids, errors = self.db_service.upsert_records(
                "game_night_comments",
                [({}, data_fields)],
            )
            if errors:
                raise HTTPException(status_code=500, detail=f"Failed to post comment: {errors[0]['error']}")

            return {"message": "Comment posted successfully", "comment_id": successful_ids[0]}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to post comment: {str(e)}")

    def _delete_discussion_comment(self, comment_id: int, current_user: dict):
        try:
            conn = self.db_service.get_connection()
            try:
                from psycopg2 import sql
                with conn.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("DELETE FROM game_night_comments WHERE id = %s RETURNING id"),
                        [comment_id],
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise HTTPException(status_code=404, detail=f"Comment {comment_id} not found")
                    conn.commit()
            finally:
                conn.close()
            return {"message": "Comment deleted successfully", "comment_id": comment_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete comment: {str(e)}")
