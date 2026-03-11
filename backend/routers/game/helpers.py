"""Helper functions for game routes"""

from fastapi import HTTPException
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db_utils import DatabaseService


def upsert_game_to_db(
    db_service: "DatabaseService",
    key_fields: dict,
    data_fields: dict,
    error_message: str = "Failed to upsert game"
) -> int:
    """
    Helper function to upsert a game record to the database.
    
    Args:
        db_service: Database service instance
        key_fields: Key fields for upsert (empty dict for insert-only)
        data_fields: Data fields to insert/update
        error_message: Custom error message if upsert fails
        
    Returns:
        The game_id of the inserted/updated game
        
    Raises:
        HTTPException: If upsert fails
    """
    record = (key_fields, data_fields)
    successful_ids, errors = db_service.upsert_records("games", [record])
    
    if errors:
        raise HTTPException(
            status_code=500,
            detail=f"{error_message}: {errors[0]['error']}"
        )
    
    game_id = successful_ids[0]
    return game_id
