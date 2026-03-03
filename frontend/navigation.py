from browser import document, window


class Navigation:
    """Handles navigation and section display"""

    def __init__(self, current_user, user_admin, games_grid, user_login):
        """
        Initialize the Navigation class

        Args:
            current_user: CurrentUser instance for accessing user info
            user_admin: UserAdmin instance for loading users
            games_grid: GamesGrid instance for loading games
            user_login: UserLogin instance for user operations
        """
        self.current_user = current_user
        self.user_admin = user_admin
        self.games_grid = games_grid
        self.user_login = user_login
        self.current_user.update_navigation = self.update_navigation

    def has_authorization(self, permission):
        """Check if current user has a specific authorization"""
        return (
            self.current_user.current_user_info
            and self.current_user.current_user_info.get("authorizations", {}).get(permission, False)
        )

    def set_element_visibility(self, element_id, visible):
        """Set visibility of a DOM element"""
        element = document.get(selector=f"#{element_id}")
        if element:
            element[0].style.display = "block" if visible else "none"

    def update_navigation(self):
        """Update navigation links and display section based on authentication status and URL hash"""
        # Get navigation elements
        logout_container = document.select(".logout-container")
        login_container = document.select(".login-container")
        login_link = document.get(selector="a[href='#login']")
        
        # Reset navigation visibility
        self.set_element_visibility("admin_nav", False)
        self.set_element_visibility("games_nav", False)

        if self.current_user.logged_in:
            username = self.current_user.current_user_info.get("username", "unknown user")
            
            if username == "unknown user":
                # Not fully authenticated
                login_link[0].text = "Login"
                logout_container[0].style.display = "none"
                login_container[0].style.display = "block"
            else:
                # Fully authenticated - show username and nav items based on permissions
                login_link[0].text = username
                logout_container[0].style.display = "block"
                login_container[0].style.display = "none"
                
                # Show navigation items based on authorizations
                self.set_element_visibility("admin_nav", self.has_authorization("is_admin"))
                self.set_element_visibility("games_nav", 
                    self.has_authorization("is_contributor") or self.has_authorization("is_viewer"))
        else:
            # Not logged in
            login_link[0].text = "Login"
            logout_container[0].style.display = "none"
            login_container[0].style.display = "block"

        # Handle URL hash changes and show appropriate section
        hash_value = window.location.hash[1:]  # Remove the # symbol
        
        # Hide all sections first
        sections = document.select(".content-section")
        for section in sections:
            section.style.display = "none"

        # Show the target section and load its data
        if hash_value:
            target = document.get(selector=f"#{hash_value}")
            if target:
                target[0].style.display = "block"
                
                # Load admin users when admin section is shown
                if hash_value == "admin" and self.has_authorization("is_admin"):
                    self.user_admin.load_users()
                
                # Handle games section
                if hash_value == "games":
                    # Show contributor forms
                    is_contributor = self.has_authorization("is_contributor")
                    self.set_element_visibility("add-game-container", is_contributor)
                    self.set_element_visibility("add-game-by-bgg-container", is_contributor)
                    self.set_element_visibility("csv-upload-container", is_contributor)
                    
                    # Load games for viewers and contributors
                    if self.has_authorization("is_viewer"):
                        self.set_element_visibility("games-grid-container", True)
                        self.games_grid.load_games()
                
                # Show user info on login page if logged in
                if hash_value == "login" and self.current_user.logged_in:
                    self.user_login.display_user_info(self.current_user.current_user_info)
