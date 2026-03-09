"""Game routes for game library management"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
import json
import logging
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db_utils import DatabaseService
    from auth_dependencies import AuthDependencies
    from bgg_scraper import BGGScraper
    from csv_utils import CSVService
    from vote_service import VoteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/game", tags=["game"])


class GameCreate(BaseModel):
    game_id: Optional[int] = None  # For updating existing games by ID
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    owner: Optional[str] = Field(None, min_length=1, max_length=255)
    min_players: Optional[int] = Field(None, ge=1)
    max_players: Optional[int] = Field(None, ge=1)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=2000)
    tags: Optional[List[str]] = None
    image_url: Optional[str] = Field(None, max_length=25000)
    bgg_link: Optional[str] = Field(None, max_length=500)
    bgg_rating: Optional[float] = Field(None, ge=0, le=9.9)
    favorited_by: Optional[List[str]] = None

    @model_validator(mode="before")
    def check_validity(cls, values):
        min_players = values.get('min_players')
        max_players = values.get('max_players')
        if min_players is not None and max_players is not None:
            if min_players > max_players:
                raise ValueError("Minimum players cannot be greater than maximum players")
        bgg_rating = values.get('bgg_rating')
        if bgg_rating is not None:
            if bgg_rating < 0 or bgg_rating > 9.9:
                raise ValueError("BGG rating must be between 0 and 9.9")
        return values


class AddGameByBGGLink(BaseModel):
    bgg_url: str = Field(..., description="BoardGameGeek URL for the game")
    owner: str = Field(..., min_length=1, max_length=255, description="Owner of the physical game")


class VoteRequest(BaseModel):
    vote: bool = Field(..., description="Vote value: true to vote, false to remove vote")


# Helper functions
def _upsert_game_to_db(
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


def setup_game_routes(
    db_service: "DatabaseService",
    auth_dependencies: "AuthDependencies",
    bgg_scraper: "BGGScraper",
    csv_service: "CSVService",
    vote_service: "VoteService",
):
    """Configure game routes with service dependencies"""

    @router.get("")
    def get_games(
        limit: int = 20,
        offset: int = 0,
        sort_by: str = None,
        sort_order: str = "ASC",
        filter_criteria: str = None,
        columns=None,
        current_user: dict = Depends(auth_dependencies._get_require_viewer_dependency()),
    ):
        """Retrieve the list of games with pagination, optional sorting, and filtering using the read_table utility method"""
        try:
            games = db_service.read_table(
                table_name="games",
                filter_criteria=filter_criteria,
                columns=columns,
                sort_by=sort_by,
                sort_order=sort_order.upper(),
                limit=limit,
                offset=offset,
            )
            total_count = db_service.read_table(
                table_name="games", filter_criteria=filter_criteria, columns=columns, count_only=True
            )
            return {"games": games, "total": total_count, "limit": limit, "offset": offset}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve games: {str(e)}"
            )

    @router.post("")
    def upsert_game(
        game: GameCreate,
        current_user: dict = Depends(
            auth_dependencies._get_require_contributor_dependency()
        ),
    ):
        """Add or update a game in the library (contributor access required). Uses bgg_link+owner or title+owner as unique key."""
        try:
            # Determine key fields for upsert
            # Prefer game_id if available, then bgg_link+owner, otherwise title+owner
            if game.game_id is not None:
                key_fields = {"id": game.game_id}
            elif game.bgg_link:
                key_fields = {"bgg_link": game.bgg_link, "owner": game.owner}
            else:
                key_fields = {"title": game.title, "owner": game.owner}

            # Build data_fields from the Pydantic model, excluding None values
            # db_utils.upsert_records will automatically filter out any remaining None values
            data_fields = game.model_dump(exclude_none=True, exclude={"game_id"})
            # Always set contributor_email
            data_fields["contributor_email"] = current_user["email"]

            # Use helper function to upsert the game
            game_id = _upsert_game_to_db(
                db_service=db_service,
                key_fields=key_fields,
                data_fields=data_fields,
                error_message="Failed to add/update game"
            )
            return {"message": "Game added/updated successfully", "game_id": game_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add/update game: {str(e)}")

    @router.post("/action/add-game-by-bgg-link")
    def upsert_game_by_bgg_link(
        request: AddGameByBGGLink,
        current_user: dict = Depends(
            auth_dependencies._get_require_contributor_dependency()
        ),
    ):
        """Add or update a game by scraping BoardGameGeek URL (contributor access required). Uses bgg_link+owner as unique key."""
        
        try:
            logger.info(f"Fetching game data from BGG URL: {request.bgg_url}")
            
            # Get and parse game data from BGG using the scraper
            game_data = bgg_scraper.get_game_data(request.bgg_url)
            
            if not game_data:
                raise HTTPException(
                    status_code=404,
                    detail="Could not extract game data from the provided BGG URL"
                )
            
            # Extract and process game information
            game_info = bgg_scraper.extract_game_info(game_data, request.bgg_url)
            
            # Store the raw JSON data in games_json table
            json_record = (
                {"bgg_id": game_info['bgg_id']},
                {
                    "title": game_info['title'],
                    "json_data": json.dumps(game_info['raw_json']),
                },
            )
            
            json_ids, json_errors = db_service.upsert_records("games_json", [json_record])
            
            if json_errors:
                logger.warning(f"Failed to store JSON data: {json_errors[0]['error']}")
            else:
                logger.info(f"Stored JSON data with ID: {json_ids[0]}")
            
            # Create game record for the games table
            # Use bgg_link + owner as key to prevent duplicates (same game, same owner)
            game_id = _upsert_game_to_db(
                db_service=db_service,
                key_fields={"bgg_link": game_info['bgg_link'], "owner": request.owner},
                data_fields={
                    "title": game_info['title'],
                    "min_players": game_info['min_players'],
                    "max_players": game_info['max_players'],
                    "description": game_info['description'],
                    "short_description": game_info['short_description'],
                    "image_url": game_info['image_url'],
                    "bgg_rating": game_info['bgg_rating'],
                    "contributor_email": current_user["email"],
                },
                error_message="Failed to add/update game to library"
            )
            logger.info(f"Successfully added/updated game '{game_info['title']}' with ID: {game_id}")
            
            return {
                "message": "Game added/updated successfully from BGG",
                "game_id": game_id,
                "bgg_id": game_info['bgg_id'],
                "title": game_info['title'],
                "owner": request.owner,
            }
            
        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"Invalid game data from BGG: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid game data: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error adding/updating game from BGG: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add/update game from BGG: {str(e)}"
            )

    @router.post("/upload-csv")
    async def upload_games_csv(
        file: UploadFile = File(...),
        current_user: dict = Depends(
            auth_dependencies._get_require_contributor_dependency()
        ),
    ):
        """Upload CSV file to bulk import games (contributor access required)"""
        try:
            return await csv_service.process_csv_upload(file, current_user["email"])

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")

    @router.get("/download-csv")
    def download_games_csv(
        current_user: dict = Depends(auth_dependencies._get_require_viewer_dependency()),
    ):
        """Download all games as a CSV file (viewer access required)"""
        try:
            # Fetch all games from the database
            games = db_service.read_table(
                table_name="games",
                columns=None,
                sort_by="id",
                sort_order="ASC",
                limit=None,
                offset=None,
            )
            
            # Generate CSV content
            csv_content = csv_service.generate_csv_download(games)
            
            # Return as downloadable file
            return StreamingResponse(
                io.StringIO(csv_content),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=games_library.csv"}
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate CSV: {str(e)}"
            )

    @router.delete("/{game_id}")
    def delete_game(
        game_id: int,
        current_user: dict = Depends(auth_dependencies._get_require_admin_dependency()),
    ):
        """Delete a game from the library (admin access required)"""
        try:
            successful_ids, errors = db_service.delete_records("games", [game_id])

            if errors:
                raise HTTPException(
                    status_code=404, detail=f"Game not found with ID {game_id}"
                )

            return {"message": "Game deleted successfully", "game_id": game_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete game: {str(e)}")

    @router.get("/{game_id}/vote")
    def get_game_votes(
        game_id: int,
        current_user: dict = Depends(
            auth_dependencies._get_require_viewer_dependency()
        ),
    ):
        """Get vote information for a game (viewer access required). Returns all votes and aggregate data."""
        try:
            return vote_service.get_game_votes(game_id, current_user["email"])
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error retrieving votes: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to retrieve votes: {str(e)}")

    @router.post("/{game_id}/vote")
    def vote_on_game(
        game_id: int,
        vote_request: VoteRequest,
        current_user: dict = Depends(
            auth_dependencies._get_require_viewer_dependency()
        ),
    ):
        """Record or remove a vote for a game (viewer access required). True = add vote, False = remove vote."""
        try:
            return vote_service.vote_on_game(game_id, current_user["email"], vote_request.vote)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error recording vote: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to record vote: {str(e)}")

    return router
