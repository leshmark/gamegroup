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


@app.post("/api/auth/request-link")
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


@app.get("/api/auth/verify-link")
def verify_auth_link(token: str):
    """Verify the one-time authentication link"""
    try:
        result = auth_service.verify_token(token)
        # TODO: Create session/JWT token here
        return {
            "message": "Authentication successful",
            "user_email": result["email"],
            "jwt": result["jwt"]
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@app.get("/api/games")
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


@app.post("/api/games")
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


@app.get("/api/tags")
def get_tags():
    """Retrieve the list of predefined tags"""
    # TODO: Implement tag retrieval
    pass


@app.post("/api/tags")
def add_tag(tag_name: str, current_user: dict = Depends(auth_dependencies._get_require_contributor_dependency())):
    """Add a new tag to the predefined list (contributor access required)"""
    # TODO: Implement tag addition with authorization check
    pass

# route to return current user info including authorizations
@app.get("/api/auth/me")
def get_current_user_info(current_user: dict = Depends(auth_dependencies._get_current_user_dependency())):
    """Get current authenticated user information"""
    try:
        return {
            "email": current_user["email"],
            "username": current_user.get("username", ""),
            "authorizations": {key: current_user[key] for key in current_user if key.startswith('is_')}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user info: {str(e)}")


@app.get("/api/admin/users")
def get_all_users(current_user: dict = Depends(auth_dependencies._get_require_admin_dependency())):
    """Get all users in the system (admin access required)"""
    try:
        users = db_service.get_all_users()
        return {
            "users": users,
            "count": len(users)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve users: {str(e)}")


@app.post("/api/admin/update-game-images")
def update_game_images(current_user: dict = Depends(auth_dependencies._get_require_admin_dependency())):
    """Update missing game image URLs from BoardGameGeek (admin access required)"""
    try:
        # Get all games missing image URLs
        games = db_service.get_games_missing_images()
        
        if not games:
            return {
                "message": "No games with missing images found",
                "total": 0,
                "successful": 0,
                "failed": 0,
                "results": []
            }
        
        results = []
        successful = 0
        failed = 0
        aborted = False
        
        # Process each game
        for game in games:
            # Abort if failure count reaches 5
            if failed >= 5:
                aborted = True
                break
            
            result = {
                "id": game["id"],
                "title": game["title"],
                "bgg_link": game["bgg_link"],
                "status": "pending"
            }
            
            try:
                # Fetch image URL from BGG
                image_url = bgg_scraper.get_game_image_url(game["bgg_link"])
                
                if image_url:
                    # Update database
                    db_service.update_game_image_url(game["id"], image_url)
                    result["status"] = "success"
                    result["image_url"] = image_url
                    successful += 1
                else:
                    result["status"] = "failed"
                    result["error"] = "No image found on BGG page"
                    failed += 1
                    
            except ValueError as e:
                result["status"] = "failed"
                result["error"] = str(e)
                failed += 1
            except Exception as e:
                result["status"] = "failed"
                result["error"] = f"Error: {str(e)}"
                failed += 1
            
            results.append(result)
        
        message = "Image update process completed"
        if aborted:
            message = "Image update process aborted after 5 failures"
        
        return {
            "message": message,
            "total": len(games),
            "processed": len(results),
            "successful": successful,
            "failed": failed,
            "aborted": aborted,
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update game images: {str(e)}")


@app.post("/api/games/upload-csv")
async def upload_games_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(auth_dependencies._get_require_contributor_dependency())
):
    """Upload CSV file to bulk import games (contributor access required)"""
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")
        
        # Read file content
        content = await file.read()
        decoded_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(decoded_content))
        
        # Validate required columns
        required_columns = ['title', 'owner', 'min_players', 'max_players']
        if not all(col in csv_reader.fieldnames for col in required_columns):
            raise HTTPException(
                status_code=400,
                detail=f"CSV must contain columns: {', '.join(required_columns)}"
            )
        
        # Process each row
        games_added = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # start=2 because row 1 is header
            try:
                # Validate and convert data
                min_players = int(row['min_players'])
                max_players = int(row['max_players'])
                
                if min_players > max_players:
                    errors.append(f"Row {row_num}: min_players cannot be greater than max_players")
                    continue
                
                # Add game to database
                game_id = db_service.add_game(
                    title=row['title'],
                    owner=row['owner'],
                    min_players=min_players,
                    max_players=max_players,
                    contributor_email=current_user["email"],
                    description=row.get('description'),
                    tags=row.get('tags', '').split(',') if row.get('tags') else None,
                    image_url=row.get('image_url'),
                    bgg_link=row.get('bgg_link'),
                    bgg_rating=float(row['bgg_rating']) if row.get('bgg_rating') else None
                )
                games_added += 1
                
            except ValueError as e:
                errors.append(f"Row {row_num}: Invalid data format - {str(e)}")
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        return {
            "message": f"CSV processed successfully",
            "games_added": games_added,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process CSV: {str(e)}")
