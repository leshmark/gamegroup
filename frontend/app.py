from browser import document, window
from auth import Auth
from game_image_updater import GameImageUpdater
from user_login import UserLogin
from user_admin import UserAdmin
from games_library import GamesLibrary
from games_grid import GamesGrid
from navigation import Navigation
from current_user import CurrentUser


class App:
    """Main application class for managing navigation and authentication"""

    def __init__(self):
        """Initialize the application and bind event handlers"""
        # Create independent components
        self.user_admin = UserAdmin()
        self.image_updater = GameImageUpdater()
        self.current_user = CurrentUser()
        
        # Create user_login (navigation callback will be set later)
        self.user_login = UserLogin(Auth(), None, self.current_user)
        
        # Create games_grid with current_user, then games_library
        self.games_grid = GamesGrid(self.current_user)
        self.games_library = GamesLibrary(self.games_grid)
        
        # Create navigation with all dependencies ready
        self.navigation = Navigation(
            self.current_user, 
            self.user_admin, 
            self.games_grid, 
            self.user_login
        )
        
        # Initialize and start
        self.current_user.get_current_user_info()
        self.bind_events()
        self.navigation.update_navigation()

    def logged_in(self):
        """Check if the user is logged in by verifying the presence of a JWT token"""
        token = window.localStorage.getItem("auth_token") or None
        return token is not None

    def bind_events(self):
        """Bind all event handlers"""
        document["login-form"].bind("submit", self.user_login.handle_login)
        document["logout-btn"].bind("click", self.user_login.handle_logout)
        document["add-game-btn"].bind("click", lambda e: self.games_library.show_add_game_form())
        document["add-game-by-bgg-btn"].bind("click", lambda e: self.games_library.show_add_game_by_bgg_form())
        document["upload-csv-btn"].bind("click", lambda e: self.games_library.show_csv_upload_form())
        document["sort-select"].bind("change", self.games_grid.handle_sort_change)
        document["sort-direction-btn"].bind(
            "click", self.games_grid.handle_sort_direction_change
        )
        document["update-images-btn"].bind(
            "click", self.image_updater.update_game_images
        )
        window.bind("hashchange", lambda e: self.navigation.update_navigation())


# Initialize the application
app = App()
