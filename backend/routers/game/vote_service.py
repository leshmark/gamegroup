import logging
from typing import Dict, Any
from database_service import DatabaseService

logger = logging.getLogger(__name__)


class VoteService:
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
    
    def vote_on_game(self, game_id: int, user_email: str, vote: bool) -> Dict[str, Any]:
        """
        Record or remove a vote for a game.
        
        Args:
            game_id: The ID of the game to vote on
            user_email: The email of the user voting
            vote: True to add vote, False to remove vote
            
        Returns:
            Dictionary with vote result information
            
        Raises:
            ValueError: If game not found or vote operation fails
        """
        # Verify game exists
        games = self.db_service.read_table(
            "games",
            filter_criteria=f"id = {game_id}",
            limit=1
        )
        
        if not games:
            raise ValueError(f"Game with ID {game_id} not found")
        
        if vote:
            return self._add_vote(game_id, user_email, games[0])
        else:
            return self._remove_vote(game_id, user_email)
    
    def _add_vote(self, game_id: int, user_email: str, game: dict) -> Dict[str, Any]:
        """Add a vote for a game"""
        key_fields = {
            "game_id": game_id,
            "user_email": user_email
        }
        
        update_fields = {
            "vote": 1  # Store as 1 for presence
        }
        
        # Upsert the vote
        successful_ids, errors = self.db_service.upsert_records(
            "game_votes",
            [(key_fields, update_fields)]
        )
        
        if errors:
            logger.error(f"Failed to record vote: {errors}")
            raise ValueError(f"Failed to record vote: {errors[0].get('error', 'Unknown error')}")
        
        vote_id = successful_ids[0] if successful_ids else None
        
        # Increment the next_play_vote_count in the games table
        game_key = {"id": game_id}
        game_update = {"next_play_vote_count": (game.get("next_play_vote_count", 0) or 0) + 1}
        _, game_errors = self.db_service.upsert_records("games", [(game_key, game_update)])
        
        if game_errors:
            logger.error(f"Failed to update vote count: {game_errors}")
            # Don't fail the request, just log the error
        
        logger.info(f"User {user_email} voted on game {game_id}")
        
        return {
            "message": "Vote recorded successfully",
            "vote_id": vote_id,
            "game_id": game_id,
            "voted": True
        }
    
    def _remove_vote(self, game_id: int, user_email: str) -> Dict[str, Any]:
        """Remove a vote for a game"""
        # Find the vote record to delete
        votes = self.db_service.read_table(
            "game_votes",
            filter_criteria=f"game_id = {game_id} AND user_email = '{user_email}'",
            limit=1
        )
        
        if not votes:
            # No vote to remove
            return {
                "message": "No vote to remove",
                "game_id": game_id,
                "voted": False
            }
        
        vote_id = votes[0].get("id")
        
        # Delete the vote
        successful_ids, errors = self.db_service.delete_records("game_votes", [vote_id])
        
        if errors:
            logger.error(f"Failed to delete vote: {errors}")
            raise ValueError(f"Failed to delete vote: {errors[0].get('error', 'Unknown error')}")
        
        # Decrement the next_play_vote_count in the games table
        game = self.db_service.read_table(
            "games",
            filter_criteria=f"id = {game_id}",
            limit=1
        )
        
        if game:
            current_count = (game[0].get("next_play_vote_count", 0) or 0)
            new_count = max(0, current_count - 1)  # Ensure it doesn't go negative
            game_key = {"id": game_id}
            game_update = {"next_play_vote_count": new_count}
            _, game_errors = self.db_service.upsert_records("games", [(game_key, game_update)])
            
            if game_errors:
                logger.error(f"Failed to update vote count: {game_errors}")
                # Don't fail the request, just log the error
        
        logger.info(f"User {user_email} removed vote from game {game_id}")
        
        return {
            "message": "Vote removed successfully",
            "game_id": game_id,
            "voted": False
        }
    
    def get_game_votes(self, game_id: int, user_email: str = None) -> Dict[str, Any]:
        """
        Get vote information for a game.
        
        Args:
            game_id: The ID of the game
            user_email: Optional email to check if this user has voted
            
        Returns:
            Dictionary with vote information
            
        Raises:
            ValueError: If game not found
        """
        # Verify game exists
        games = self.db_service.read_table(
            "games",
            filter_criteria=f"id = {game_id}",
            limit=1
        )
        
        if not games:
            raise ValueError(f"Game with ID {game_id} not found")
        
        # Get all votes for this game
        votes = self.db_service.read_table(
            "game_votes",
            filter_criteria=f"game_id = {game_id}",
            sort_by="created_at",
            sort_order="DESC"
        )
        
        # Calculate aggregate data
        total_votes = len(votes)
        
        # Check if current user has voted (if user_email provided)
        user_has_voted = False
        if user_email:
            for vote in votes:
                if vote.get("user_email") == user_email:
                    user_has_voted = True
                    break
        
        return {
            "game_id": game_id,
            "total_votes": total_votes,
            "user_has_voted": user_has_voted,
            "votes": votes
        }
