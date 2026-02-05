# FastAPI app with get homepage route

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import os
import json
from db_utils import DatabaseService
from auth_utils import AuthService
from email_utils import EmailService
from auth_dependencies import AuthDependencies

app = FastAPI()

# Initialize services
db_service = DatabaseService()
auth_service = AuthService(db_service)
email_service = EmailService()
auth_dependencies = AuthDependencies()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Initialize database tables on startup"""
    try:
        db_service.create_auth_links_table()
        db_service.create_games_table()
        db_service.create_users_table()
        db_service.Initialize_users_table()
        print("Database tables initialized successfully")

    except Exception as e:
        print(f"Error during startup: {e}")


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


@app.post("/auth/request-link")
def request_auth_link(auth_request: AuthRequest):
    """Request a one-time authentication link via email"""
    email = auth_request.email
    
    # Generate token, store it, and build magic link
    try:
        magic_link = auth_service.build_magic_link(email, minutes=15)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Send email
    email_service.send_auth_email(email, magic_link)
    
    return {"message": "Authentication link sent to your email"}


@app.get("/auth/verify-link")
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


@app.get("/games")
def get_games(sort_by: str = None, filter_by: str = None):
    """Retrieve the list of games (with optional sorting and filtering parameters)"""
    # TODO: Implement game retrieval with sorting and filtering
    pass


@app.post("/games")
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


@app.get("/tags")
def get_tags():
    """Retrieve the list of predefined tags"""
    # TODO: Implement tag retrieval
    pass


@app.post("/tags")
def add_tag(tag_name: str, current_user: dict = Depends(auth_dependencies._get_require_contributor_dependency())):
    """Add a new tag to the predefined list (contributor access required)"""
    # TODO: Implement tag addition with authorization check
    pass

# route to return current user info including authorizations
@app.get("/auth/me")
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


@app.get("/admin/users")
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
