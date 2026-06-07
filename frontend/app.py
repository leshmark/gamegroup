from browser import window
from browser.local_storage import storage
from auth import Auth
from game_library_updater import GameLibraryUpdater
from user_login import UserLogin
from user_admin import UserAdmin
from games_library import GamesLibrary
from games_grid import GamesGrid
from navigation import Navigation
from current_user import CurrentUser
from play_log import PlayLog


class App:
    """Main application class for managing navigation and authentication"""

    def __init__(self):
        """Initialize the application and bind event handlers"""
        # Create independent components
        self.user_admin = UserAdmin()
        self.library_updater = GameLibraryUpdater()
        self.current_user = CurrentUser(on_ready=self._on_user_ready)

    def _on_user_ready(self):
        """Called when current user info fetch completes; initialize dependent components."""
        # Create user_login
        self.user_login = UserLogin(Auth(), self.current_user)

        # Create games_grid with current_user, then games_library
        self.games_grid = GamesGrid(self.current_user)
        self.games_library = GamesLibrary(self.games_grid)

        # Create play log component
        self.play_log = PlayLog(self.current_user)

        # Create navigation with all dependencies ready
        self.navigation = Navigation(
            self.current_user,
            self.user_admin,
            self.games_grid,
            self.user_login,
            self.play_log,
        )

        self.navigation.update_navigation()

    def logged_in(self):
        """Check if the user is logged in by verifying the presence of a JWT token"""
        token = storage.get("auth_token", None)
        return token is not None


# Initialize the application
app = App()
