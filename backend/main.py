"""
Game Group Backend API - Main Application Entry Point

This module initializes and configures the FastAPI application for the Game Group backend service.
It sets up logging, CORS middleware, database connections, and registers all API routers.

Routers included:
    - admin: Administrative endpoints for user and system management
    - auth: Authentication and user session management
    - game: Game library management and BoardGameGeek integration
    - game_night: Game night event tracking and logging
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from database_service import DatabaseService

# Import routers from the routers package
from routers import (
    admin_router,
    auth_router,
    game_router,
    game_night_router,
)


class Application:
    """
    Main application class that encapsulates the FastAPI app setup and configuration.
    
    This class handles:
    - Logging configuration
    - Database service initialization
    - FastAPI app creation and configuration
    - Router registration
    """
    
    def __init__(self):
        """
        Initialize the Application instance.
        
        Sets up logging, creates the database service, and creates the FastAPI app.
        """
        self._configure_logging()
        self.db_service = DatabaseService()
        self.app = self._create_app()

    def _configure_logging(self):
        """
        Configure application logging based on environment variables.
        
        Reads LOG_LEVEL from environment (defaults to INFO) and sets up
        console logging with a standardized format including timestamp,
        logger name, level, and message.
        """
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def _create_app(self) -> FastAPI:
        """
        Create and configure the FastAPI application instance.
        
        Returns:
            FastAPI: Configured FastAPI application instance
        """
        app = FastAPI()
        self._configure_cors(app)
        self._register_startup_events(app)
        self._include_routers(app)
        return app

    def _configure_cors(self, app: FastAPI):
        """
        Configure Cross-Origin Resource Sharing (CORS) middleware.
        
        Sets allowed origins from the ALLOWED_ORIGINS environment variable
        (comma-separated list). Defaults to local development origins.
        Allows all HTTP methods and headers, and enables credentials.
        
        Args:
            app: The FastAPI application instance to configure
        """
        allowed_origins = os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
        ).split(",")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _register_startup_events(self, app: FastAPI):
        """
        Register application startup event handlers.
        
        Registers an event handler that runs when the application starts up.
        This handler initializes the database tables by calling the database
        service's initialize_database method.
        
        Args:
            app: The FastAPI application instance
        """
        @app.on_event("startup")
        def startup_event():
            """Initialize database tables on startup"""
            try:
                self.db_service.initialize_database()
            except Exception as e:
                self.logger.error(f"Error during startup: {e}", exc_info=True)

    def _include_routers(self, app: FastAPI):
        """
        Register all API routers with the FastAPI application.
        
        Includes routers for:
        - Admin endpoints (user management, system administration)
        - Authentication endpoints (login, registration, token management)
        - Game endpoints (library management, BGG scraping)
        - Game night endpoints (event tracking, logging)
        
        Args:
            app: The FastAPI application instance
        """
        app.include_router(admin_router)
        app.include_router(auth_router)
        app.include_router(game_router)
        app.include_router(game_night_router)


# Create the application instance and expose the FastAPI app
application = Application()
app = application.app
