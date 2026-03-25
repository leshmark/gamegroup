# FastAPI app with get homepage route

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from database_service import DatabaseService

# Import routers
from routers import (
    admin_router,
    auth_router,
    game_router,
    play_log_router,
    tag_router,
)


class Application:
    def __init__(self):
        self._configure_logging()
        self.db_service = DatabaseService()
        self.app = self._create_app()

    def _configure_logging(self):
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def _create_app(self) -> FastAPI:
        app = FastAPI()
        self._configure_cors(app)
        self._register_startup_events(app)
        self._include_routers(app)
        return app

    def _configure_cors(self, app: FastAPI):
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
        @app.on_event("startup")
        def startup_event():
            """Initialize database tables on startup"""
            try:
                self.db_service.initialize_database()
            except Exception as e:
                self.logger.error(f"Error during startup: {e}", exc_info=True)

    def _include_routers(self, app: FastAPI):
        app.include_router(admin_router)
        app.include_router(auth_router)
        app.include_router(game_router)
        app.include_router(play_log_router)
        app.include_router(tag_router)


application = Application()
app = application.app
