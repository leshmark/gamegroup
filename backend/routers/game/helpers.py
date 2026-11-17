"""Helper functions for game routes"""

from datetime import datetime, timezone
from fastapi import HTTPException
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from database_service import DatabaseService


def upsert_game_to_db(
    db_service: "DatabaseService",
    key_fields: dict,
    data_fields: dict,
    error_message: str = "Failed to upsert game"
) -> str:
    """
    Helper function to upsert a game record to the database.
    
    Args:
        db_service: Database service instance
        key_fields: Key fields for upsert (empty dict for insert-only)
        data_fields: Data fields to insert/update
        error_message: Custom error message if upsert fails
        
    Returns:
        The external (GUID7 UUID) id of the inserted/updated game
        
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


def _games_users_rows(db_service: "DatabaseService", game_id: str, role: str) -> list:
    """Return the games_users rows for *game_id* with the given *role*."""
    return db_service.read_table(
        "games_users",
        filter_criteria=[
            {"col": "game_external_id", "op": "=", "val": game_id},
            {"col": "role", "op": "=", "val": role},
        ],
    )


def replace_games_users_role(
    db_service: "DatabaseService", game_id: str, role: str, emails: Optional[List[str]]
) -> None:
    """Replace all games_users rows for (game, role) with *emails*.

    ``games`` no longer stores owner/favorited_by, so the junction table is the
    single source of truth: setting the owner (or the favorite set) deletes the
    role's existing rows and inserts the new ones.  ``emails`` may be None
    (clear the role) or a list of emails.
    """
    existing = _games_users_rows(db_service, game_id, role)
    if existing:
        identifiers = [
            {
                "game_external_id": game_id,
                "user_email": row["user_email"],
                "role": role,
            }
            for row in existing
        ]
        _, errors = db_service.delete_records("games_users", identifiers)
        if errors:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to clear games_users role {role!r}: {errors[0]['error']}",
            )

    emails = [e for e in (emails or []) if e]
    if not emails:
        return

    now = datetime.now(timezone.utc)
    records = [
        (
            {"game_external_id": game_id, "user_email": email, "role": role},
            {"created_at": now},
        )
        for email in emails
    ]
    _, errors = db_service.upsert_records("games_users", records)
    if errors:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write games_users role {role!r}: {errors[0]['error']}",
        )


def add_games_users_contributor(
    db_service: "DatabaseService", game_id: str, email: str
) -> None:
    """Record *email* as a contributor on the game (idempotent).

    Unlike owner/favorite, contributors accumulate: the view surfaces the most
    recently touched contributor row as ``contributor_email``.
    """
    if not email:
        return
    record = (
        {
            "game_external_id": game_id,
            "user_email": email,
            "role": "contributor",
        },
        {"created_at": datetime.now(timezone.utc)},
    )
    _, errors = db_service.upsert_records("games_users", [record])
    if errors:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record contributor: {errors[0]['error']}",
        )


def delete_game_dependencies(db_service: "DatabaseService", game_id: str) -> None:
    """Delete the soft-linked rows that reference a game before/after deleting it.

    The ``fk_game`` FK is gone (all relationships are soft links), so deleting a
    game no longer cascades in PostgreSQL — the REST layer removes the dependent
    ``game_votes`` and ``games_users`` rows in code.
    """
    vote_rows = db_service.read_table(
        "game_votes",
        filter_criteria=[{"col": "game_external_id", "op": "=", "val": game_id}],
        columns=["external_id"],
    )
    if vote_rows:
        db_service.delete_records(
            "game_votes", [row["external_id"] for row in vote_rows]
        )

    link_rows = db_service.read_table(
        "games_users",
        filter_criteria=[{"col": "game_external_id", "op": "=", "val": game_id}],
    )
    if link_rows:
        db_service.delete_records(
            "games_users",
            [
                {
                    "game_external_id": game_id,
                    "user_email": row["user_email"],
                    "role": row["role"],
                }
                for row in link_rows
            ],
        )
