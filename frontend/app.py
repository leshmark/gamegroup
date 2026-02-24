from browser import document, window
from auth import Auth
from game_image_updater import GameImageUpdater
from user_login import UserLogin
from user_admin import UserAdmin
from games_library import GamesLibrary
from games_grid import GamesGrid
from navigation import Navigation


class App:
    """Main application class for managing navigation and authentication"""

    def __init__(self):
        """Initialize the application and bind event handlers"""
        auth_instance = Auth()
        self.image_updater = GameImageUpdater()
        self.user_admin = UserAdmin()
        self.games_grid = GamesGrid()
        self.games_library = GamesLibrary(self.games_grid)
        self.navigation = Navigation(
            None, self.user_admin, self.games_grid, self.logged_in
        )
        self.user_login = UserLogin(auth_instance, self.navigation.handle_navigation)
        # Update navigation's user_login reference after creating user_login
        self.navigation.user_login = self.user_login
        # Update games_grid's user_login reference after creating user_login
        self.games_grid.user_login = self.user_login
        self.user_login.get_current_user_info()
        self.bind_events()
        self.navigation.handle_navigation()

    def logged_in(self):
        """Check if the user is logged in by verifying the presence of a JWT token"""
        token = window.localStorage.getItem("auth_token") or None
        return token is not None

    def bind_events(self):
        """Bind all event handlers"""
        document["login-form"].bind("submit", self.user_login.handle_login)
        document["logout-btn"].bind("click", self.user_login.handle_logout)
        document["add-game-btn"].bind("click", lambda e: self.games_library.show_add_game_form())
        document["upload-csv-btn"].bind("click", lambda e: self.games_library.show_csv_upload_form())
        document["sort-select"].bind("change", self.games_grid.handle_sort_change)
        document["sort-direction-btn"].bind(
            "click", self.games_grid.handle_sort_direction_change
        )
        document["update-images-btn"].bind(
            "click", self.image_updater.update_game_images
        )
        window.bind("hashchange", lambda e: self.navigation.handle_navigation())


# Initialize the application
app = App()
