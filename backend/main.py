# FastAPI app with get homepage route

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import os
import json
import csv
import io
import logging
from db_utils import DatabaseService
from auth_utils import AuthService
from email_utils import EmailService
from auth_dependencies import AuthDependencies
from bgg_scraper import BGGScraper
from games_uploader import GamesUploader
from game_image_updater import GameImageUpdater

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize services
db_service = DatabaseService()
auth_service = AuthService(db_service)
email_service = EmailService()
auth_dependencies = AuthDependencies()
bgg_scraper = BGGScraper()
games_uploader = GamesUploader(db_service)
game_image_updater = GameImageUpdater(db_service, bgg_scraper)

# Configure CORS
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Initialize database tables on startup"""
    try:
        logger.info("Starting database initialization...")
        db_service.create_auth_links_table()
        db_service.create_games_table()
        db_service.create_users_table()
        db_service.Initialize_users_table()
        logger.info("Database tables initialized successfully")

    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)


@app.get("/")
def read_root():
    return {"Hello": "World"}


class AuthRequest(BaseModel):
    email: EmailStr


class GameCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    owner: str = Field(..., min_length=1, max_length=255)
    min_players: int = Field(..., ge=1)
    max_players: int = Field(..., ge=1)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = Field(None, max_length=25000)
    bgg_link: Optional[str] = Field(None, max_length=500)
    bgg_rating: Optional[float] = Field(None, ge=0, le=10)


@app.post("/api/admin/action/update-game-images")
def update_game_images(current_user: dict = Depends(auth_dependencies._get_require_admin_dependency())):
    """Update missing game image URLs from BoardGameGeek (admin access required)"""
    try:
        return game_image_updater.update_missing_images()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update game images: {str(e)}")


@app.get("/api/admin/authorization")
def get_authorizations(current_user: dict = Depends(auth_dependencies._get_require_admin_dependency())):
    """Get a list of all available authorizations/roles in the system (admin access required)"""
    return {
        "authorizations": [
            "is_viewer",
            "is_contributor",
            "is_admin"
        ]
    }


@app.get("/api/admin/user")
def get_all_users(current_user: dict = Depends(auth_dependencies._get_require_admin_dependency())):
    """Get one or more users in the system (admin access required)"""
    #TODO: fix this to allow filtering by email or other parameters. This will be used by the frontend admin panel to manage users.
    try:
        users = db_service.get_all_users()
        return {
            "users": users,
            "count": len(users)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve users: {str(e)}")


@app.post("/api/admin/user")
def upsert_user(user_data: dict, current_user: dict = Depends(auth_dependencies._get_require_admin_dependency())):
    """Upsert user information (admin access required)"""
    #TODO: Implement this route to allow admins to create or update user information, including their authorizations. This will be used by the frontend admin panel to manage users.
    pass


# route to return current user info including authorizations
@app.get("/api/auth/me")
def get_current_user_info(current_user: dict = Depends(auth_dependencies._get_current_user_dependency())):
    """Get current authenticated user information from JWT token, including their authorizations"""
    try:
        return {
            "email": current_user["email"],
            "username": current_user.get("username", ""),
            "authorizations": {key: current_user[key] for key in current_user if key.startswith('is_')}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user info: {str(e)}")


@app.post("/api/auth/action/request-link")
def request_auth_link(auth_request: AuthRequest):
    """Request a one-time authentication link via email"""
    email = auth_request.email
    
    # Check if user exists in the database
    user = db_service.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Email address not found in user table")
    
    # Generate token, store it, and build magic link
    try:
        magic_link = auth_service.build_magic_link(email, minutes=15)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Send email
    email_service.send_auth_email(email, magic_link)
    
    return {"message": "Authentication link sent to your email"}


@app.get("/api/auth/action/verify-link")
def verify_auth_link(token: str):
    """Verify the one-time authentication link"""
    try:
        result = auth_service.verify_token(token)
        return {
            "message": "Authentication successful",
            "user_email": result["email"],
            "jwt": result["jwt"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@app.get("/api/game")
def get_games(
    limit: int = 20, 
    offset: int = 0, 
    sort_by: str = None,
    current_user: dict = Depends(auth_dependencies._get_require_viewer_dependency())
):
    """Retrieve the list of games with pagination"""
    try:
        # Validate parameters
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
        if offset < 0:
            raise HTTPException(status_code=400, detail="Offset must be non-negative")
        
        result = db_service.get_games(limit=limit, offset=offset, sort_by=sort_by)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve games: {str(e)}")


@app.post("/api/game")
def add_game(game: GameCreate, current_user: dict = Depends(auth_dependencies._get_require_contributor_dependency())):
    """Add a new game to the library (contributor access required)"""
    try:
        # Validate min/max players
        if game.min_players > game.max_players:
            raise HTTPException(
                status_code=400,
                detail="Minimum players cannot be greater than maximum players"
            )
        
        game_id = db_service.add_game(
            title=game.title,
            owner=game.owner,
            min_players=game.min_players,
            max_players=game.max_players,
            contributor_email=current_user["email"],
            description=game.description,
            tags=game.tags,
            image_url=game.image_url,
            bgg_link=game.bgg_link,
            bgg_rating=game.bgg_rating
        )
        
        return {
            "message": "Game added successfully",
            "game_id": game_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add game: {str(e)}")


@app.post("/api/game/upload-csv")
async def upload_games_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(auth_dependencies._get_require_contributor_dependency())
):
    """Upload CSV file to bulk import games (contributor access required)"""
    try:
        return await games_uploader.process_csv_upload(file, current_user["email"])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")


@app.get("/api/tag")
def get_tags():
    """Retrieve the list of predefined tags"""
    # TODO: Implement tag retrieval
    pass


@app.post("/api/tag")
def add_tag(tag_name: str, current_user: dict = Depends(auth_dependencies._get_require_contributor_dependency())):
    """Add a new tag to the predefined list (contributor access required)"""
    # TODO: Implement tag addition with authorization check
    pass



