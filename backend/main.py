# FastAPI app with get homepage route

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from db_utils import DatabaseService
from auth_utils import AuthService
from email_utils import EmailService
from auth_dependencies import AuthDependencies
from bgg_scraper import BGGScraper
from csv_utils import CSVService
from game_image_updater import GameImageUpdater
from vote_service import VoteService

# Import router setup functions
from admin_router import setup_admin_routes
from auth_router import setup_auth_routes
from game_router import setup_game_routes
from tag_router import setup_tag_routes

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize services
db_service = DatabaseService()
auth_service = AuthService(db_service)
email_service = EmailService()
auth_dependencies = AuthDependencies()
bgg_scraper = BGGScraper()
csv_service = CSVService(db_service)
game_image_updater = GameImageUpdater(db_service, bgg_scraper)
vote_service = VoteService(db_service)

# Configure CORS
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
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
        db_service.initialize_database()
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)


# Setup and include routers
admin_router = setup_admin_routes(db_service, auth_dependencies, game_image_updater)
auth_router = setup_auth_routes(auth_service, email_service, auth_dependencies)
game_router = setup_game_routes(db_service, auth_dependencies, bgg_scraper, csv_service, vote_service)
tag_router = setup_tag_routes(auth_dependencies)

app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(game_router)
app.include_router(tag_router)
