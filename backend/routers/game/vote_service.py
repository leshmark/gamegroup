import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from database_service import DatabaseService

logger = logging.getLogger(__name__)

VOTE_WINDOW_DAYS = 14  # Votes older than this are aged out


class VoteService:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def _cutoff_time(self) -> datetime:
        """Return the oldest timestamp that is still within the active vote window."""
        return datetime.utcnow() - timedelta(days=VOTE_WINDOW_DAYS)

    def vote_on_game(self, game_id: int, user_email: str, vote: bool) -> Dict[str, Any]:
        """
        Record or remove a vote for a game.

        Votes age out after 2 weeks. A user may cast a new vote for the same game
        once their previous vote has aged out. Only the most recent vote (within the
        window) can be removed.

        Args:
            game_id: The ID of the game to vote on
            user_email: The email of the user voting
            vote: True to add vote, False to remove vote

        Returns:
            Dictionary with vote result information

        Raises:
            ValueError: If game not found or vote operation fails
        """
        games = self.db_service.read_table(
            "games",
            filter_criteria=[{"col": "id", "op": "=", "val": game_id}],
            limit=1,
        )
        if not games:
            raise ValueError(f"Game with ID {game_id} not found")

        if vote:
            return self._add_vote(game_id, user_email)
        else:
            return self._remove_vote(game_id, user_email)

    def _add_vote(self, game_id: int, user_email: str) -> Dict[str, Any]:
        """Insert a new vote, rejecting duplicates within the 2-week window."""
        cutoff = self._cutoff_time()
        active = self.db_service.read_table(
            "game_votes",
            filter_criteria=[
                {"col": "game_id", "op": "=", "val": game_id},
                {"col": "user_email", "op": "=", "val": user_email},
                {"col": "created_at", "op": ">", "val": cutoff},
            ],
            limit=1,
        )
        if active:
            raise ValueError("You have already voted for this game in the last 2 weeks")

        conn = self.db_service.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO game_votes (game_id, user_email, vote) VALUES (%s, %s, %s) RETURNING id",
                    [game_id, user_email, 1],
                )
                row = cursor.fetchone()
                vote_id = row[0] if row else None
                conn.commit()
        finally:
            conn.close()

        logger.info(f"User {user_email} voted on game {game_id}")
        return {
            "message": "Vote recorded successfully",
            "vote_id": vote_id,
            "game_id": game_id,
            "voted": True,
        }

    def _remove_vote(self, game_id: int, user_email: str) -> Dict[str, Any]:
        """Remove the user's most recent active vote (within the 2-week window)."""
        cutoff = self._cutoff_time()
        active = self.db_service.read_table(
            "game_votes",
            filter_criteria=[
                {"col": "game_id", "op": "=", "val": game_id},
                {"col": "user_email", "op": "=", "val": user_email},
                {"col": "created_at", "op": ">", "val": cutoff},
            ],
            sort_by="created_at",
            sort_order="DESC",
            limit=1,
        )
        if not active:
            return {
                "message": "No active vote to remove",
                "game_id": game_id,
                "voted": False,
            }

        vote_id = active[0].get("id")
        successful_ids, errors = self.db_service.delete_records("game_votes", [vote_id])
        if errors:
            logger.error(f"Failed to delete vote: {errors}")
            raise ValueError(f"Failed to delete vote: {errors[0].get('error', 'Unknown error')}")

        logger.info(f"User {user_email} removed vote from game {game_id}")
        return {
            "message": "Vote removed successfully",
            "game_id": game_id,
            "voted": False,
        }

    def get_game_votes(self, game_id: int, user_email: str = None) -> Dict[str, Any]:
        """
        Get vote information for a game.

        Only votes within the active 2-week window are counted.

        Args:
            game_id: The ID of the game
            user_email: Optional email to check if this user has an active vote

        Returns:
            Dictionary with vote information

        Raises:
            ValueError: If game not found
        """
        games = self.db_service.read_table(
            "games",
            filter_criteria=[{"col": "id", "op": "=", "val": game_id}],
            limit=1,
        )
        if not games:
            raise ValueError(f"Game with ID {game_id} not found")

        cutoff = self._cutoff_time()
        active_votes = self.db_service.read_table(
            "game_votes",
            filter_criteria=[
                {"col": "game_id", "op": "=", "val": game_id},
                {"col": "created_at", "op": ">", "val": cutoff},
            ],
            sort_by="created_at",
            sort_order="DESC",
        )

        total_votes = len(active_votes)
        user_has_voted = (
            any(v.get("user_email") == user_email for v in active_votes)
            if user_email
            else False
        )

        return {
            "game_id": game_id,
            "total_votes": total_votes,
            "user_has_voted": user_has_voted,
            "votes": active_votes,
        }
