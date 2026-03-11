# FastAPI app with get homepage route

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from db_utils import DatabaseService

# Import routers
from routers import (
    admin_router,
    auth_router,
    game_router,
    tag_router,
)

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Initialize database service for startup
db_service = DatabaseService()

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


# Include routers
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(game_router)
app.include_router(tag_router)
