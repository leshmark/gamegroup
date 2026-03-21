"""Game routes for game library management"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
import json
import logging
import io

from .models import GameCreate, AddGameByBGGLink, VoteRequest
from .helpers import upsert_game_to_db
from .bgg_scraper import BGGScraper
from .csv_service import CSVService
from .vote_service import VoteService
from database_service import DatabaseService
from auth_dependencies import AuthDependencies

logger = logging.getLogger(__name__)


class GameRouter:
    def __init__(self):
        self.db_service = DatabaseService()
        self.auth_dependencies = AuthDependencies()
        self.bgg_scraper = BGGScraper()
        self.csv_service = CSVService(self.db_service)
        self.vote_service = VoteService(self.db_service)
        self.router = self._build_router()

    def _build_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1/game", tags=["game"])
        require_viewer = self.auth_dependencies._get_require_viewer_dependency()
        require_contributor = self.auth_dependencies._get_require_contributor_dependency()
        require_admin = self.auth_dependencies._get_require_admin_dependency()

        @router.get("")
        def get_games(
            limit: int = 20,
            offset: int = 0,
            sort_by: str = None,
            sort_order: str = "ASC",
            filter_criteria: str = None,
            columns=None,
            current_user: dict = Depends(require_viewer),
        ):
            """Retrieve the list of games with pagination, optional sorting, and filtering using the read_table utility method"""
            return self._get_games(limit, offset, sort_by, sort_order, filter_criteria, columns, current_user)

        @router.post("")
        def upsert_game(
            game: GameCreate,
            current_user: dict = Depends(require_contributor),
        ):
            """Add or update a game in the library (contributor access required). Uses bgg_link+owner or title+owner as unique key."""
            return self._upsert_game(game, current_user)

        @router.post("/action/add-game-by-bgg-link")
        def upsert_game_by_bgg_link(
            request: AddGameByBGGLink,
            current_user: dict = Depends(require_contributor),
        ):
            """Add or update a game by scraping BoardGameGeek URL (contributor access required). Uses bgg_link+owner as unique key."""
            return self._upsert_game_by_bgg_link(request, current_user)

        @router.post("/upload-csv")
        async def upload_games_csv(
            file: UploadFile = File(...),
            current_user: dict = Depends(require_contributor),
        ):
            """Upload CSV file to bulk import games (contributor access required)"""
            return await self._upload_games_csv(file, current_user)

        @router.get("/download-csv")
        def download_games_csv(
            current_user: dict = Depends(require_viewer),
        ):
            """Download all games as a CSV file (viewer access required)"""
            return self._download_games_csv(current_user)

        @router.delete("/{game_id}")
        def delete_game(
            game_id: int,
            current_user: dict = Depends(require_admin),
        ):
            """Delete a game from the library (admin access required)"""
            return self._delete_game(game_id, current_user)

        @router.get("/{game_id}/vote")
        def get_game_votes(
            game_id: int,
            current_user: dict = Depends(require_viewer),
        ):
            """Get vote information for a game (viewer access required). Returns all votes and aggregate data."""
            return self._get_game_votes(game_id, current_user)

        @router.post("/{game_id}/vote")
        def vote_on_game(
            game_id: int,
            vote_request: VoteRequest,
            current_user: dict = Depends(require_viewer),
        ):
            """Record or remove a vote for a game (viewer access required). True = add vote, False = remove vote."""
            return self._vote_on_game(game_id, vote_request, current_user)

        return router

    def _get_games(self, limit, offset, sort_by, sort_order, filter_criteria, columns, current_user):
        try:
            games = self.db_service.read_table(
                table_name="games",
                filter_criteria=filter_criteria,
                columns=columns,
                sort_by=sort_by,
                sort_order=sort_order.upper(),
                limit=limit,
                offset=offset,
            )
            total_count = self.db_service.read_table(
                table_name="games", filter_criteria=filter_criteria, columns=columns, count_only=True
            )
            return {"games": games, "total": total_count, "limit": limit, "offset": offset}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve games: {str(e)}"
            )

    def _upsert_game(self, game: GameCreate, current_user: dict):
        try:
            if game.game_id is not None:
                key_fields = {"id": game.game_id}
            elif game.bgg_link:
                key_fields = {"bgg_link": game.bgg_link, "owner": game.owner}
            else:
                key_fields = {"title": game.title, "owner": game.owner}

            data_fields = game.model_dump(exclude_none=True, exclude={"game_id"})
            data_fields["contributor_email"] = current_user["email"]

            game_id = upsert_game_to_db(
                db_service=self.db_service,
                key_fields=key_fields,
                data_fields=data_fields,
                error_message="Failed to add/update game"
            )
            return {"message": "Game added/updated successfully", "game_id": game_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to add/update game: {str(e)}")

    def _upsert_game_by_bgg_link(self, request: AddGameByBGGLink, current_user: dict):
        try:
            logger.info(f"Fetching game data from BGG URL: {request.bgg_url}")

            game_data = self.bgg_scraper.get_game_data(request.bgg_url)

            if not game_data:
                raise HTTPException(
                    status_code=404,
                    detail="Could not extract game data from the provided BGG URL"
                )

            game_info = self.bgg_scraper.extract_game_info(game_data, request.bgg_url)

            json_record = (
                {"bgg_id": game_info['bgg_id']},
                {
                    "title": game_info['title'],
                    "json_data": json.dumps(game_info['raw_json']),
                },
            )

            json_ids, json_errors = self.db_service.upsert_records("games_json", [json_record])

            if json_errors:
                logger.warning(f"Failed to store JSON data: {json_errors[0]['error']}")
            else:
                logger.info(f"Stored JSON data with ID: {json_ids[0]}")

            game_id = upsert_game_to_db(
                db_service=self.db_service,
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

    async def _upload_games_csv(self, file: UploadFile, current_user: dict):
        try:
            return await self.csv_service.process_csv_upload(file, current_user["email"])
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")

    def _download_games_csv(self, current_user: dict):
        try:
            games = self.db_service.read_table(
                table_name="games",
                columns=None,
                sort_by="id",
                sort_order="ASC",
                limit=None,
                offset=None,
            )

            csv_content = self.csv_service.generate_csv_download(games)

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

    def _delete_game(self, game_id: int, current_user: dict):
        try:
            successful_ids, errors = self.db_service.delete_records("games", [game_id])

            if errors:
                raise HTTPException(
                    status_code=404, detail=f"Game not found with ID {game_id}"
                )

            return {"message": "Game deleted successfully", "game_id": game_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete game: {str(e)}")

    def _get_game_votes(self, game_id: int, current_user: dict):
        try:
            return self.vote_service.get_game_votes(game_id, current_user["email"])
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error retrieving votes: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to retrieve votes: {str(e)}")

    def _vote_on_game(self, game_id: int, vote_request: VoteRequest, current_user: dict):
        try:
            return self.vote_service.vote_on_game(game_id, current_user["email"], vote_request.vote)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Error recording vote: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to record vote: {str(e)}")


_handler = GameRouter()
router = _handler.router
