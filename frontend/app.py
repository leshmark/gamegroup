from browser import window, timer
from browser.local_storage import storage
from auth import Auth
from game_library_updater import GameLibraryUpdater
from user_login import UserLogin
from user_admin import UserAdmin
from games_library import GamesLibrary
from games_grid import GamesGrid
from navigation import Navigation
from current_user import CurrentUser
from game_night import GameNight


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

        # Create game night component
        self.game_night = GameNight(self.current_user)

        # Create navigation with all dependencies ready
        self.navigation = Navigation(
            self.current_user,
            self.user_admin,
            self.games_grid,
            self.user_login,
            self.game_night,
        )

        self.navigation.update_navigation()


# Poll for auth_token changes every 5 seconds and reload if it changes
_previous_auth_token = storage.get("auth_token", None)
_poll_interval = None

def _check_auth_token():
    """Check for changes in authentication token and reload page if changed."""
    global _previous_auth_token, _poll_interval
    current_token = storage.get("auth_token", None)
    if current_token != _previous_auth_token:
        timer.clear_interval(_poll_interval)
        window.location.reload()
    _previous_auth_token = current_token

_poll_interval = timer.set_interval(_check_auth_token, 5000)

# Initialize the application
app = App()
