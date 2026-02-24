from browser import document, window


class Navigation:
    """Handles navigation and section display"""

    def __init__(self, user_login, user_admin, games_grid, logged_in_callback):
        """
        Initialize the Navigation class

        Args:
            user_login: UserLogin instance for accessing user info
            user_admin: UserAdmin instance for loading users
            games_grid: GamesGrid instance for loading games
            logged_in_callback: Callback function to check if user is logged in
        """
        self.user_login = user_login
        self.user_admin = user_admin
        self.games_grid = games_grid
        self.logged_in_callback = logged_in_callback

    def show_section(self, section_id):
        """Show the specified section and hide all others"""
        sections = document.select(".content-section")
        for section in sections:
            section.style.display = "none"

        if section_id:
            target = document.get(selector=f"#{section_id}")
            if target:
                target[0].style.display = "block"
                # Load users when admin section is shown
                if (
                    section_id == "admin"
                    and self.user_login.current_user_info
                    and self.user_login.current_user_info["authorizations"].get(
                        "is_admin"
                    )
                ):
                    self.user_admin.load_users()
                # Show CSV upload form when games section is shown and user is contributor
                if (
                    section_id == "games"
                    and self.user_login.current_user_info
                    and self.user_login.current_user_info["authorizations"].get(
                        "is_contributor"
                    )
                ):
                    self.show_add_game_form()
                    self.show_csv_upload_form()
                # Load games when games section is shown
                if (
                    section_id == "games"
                    and self.user_login.current_user_info
                    and self.user_login.current_user_info["authorizations"].get(
                        "is_viewer"
                    )
                ):
                    self.show_games()
                    self.games_grid.load_games()

    def handle_navigation(self):
        """Update navigation links based on authentication status and user info"""
        logout_container = document.select(".logout-container")
        login_container = document.select(".login-container")
        login_link = document.get(selector="a[href='#login']")
        admin_nav = document.get(selector="#admin_nav")
        admin_nav[0].style.display = "none"

        if self.logged_in_callback():
            login_link[0].text = self.user_login.current_user_info.get(
                "username", "unknown user"
            )
            logout_container[0].style.display = "block"
            login_container[0].style.display = "none"
            if self.user_login.current_user_info and self.user_login.current_user_info[
                "authorizations"
            ].get("is_admin"):
                admin_nav[0].style.display = "block"
        else:
            login_link[0].text = "Login"
            logout_container[0].style.display = "none"
            login_container[0].style.display = "block"
            admin_nav[0].style.display = "none"

        """Handle URL hash changes for navigation"""
        hash_value = window.location.hash[1:]  # Remove the # symbol
        self.show_section(hash_value)

    def show_games(self):
        """Show games section for viewers and contributors"""
        games_section = document["games-grid-container"]
        games_section.style.display = "block"

    def show_add_game_form(self):
        """Show manual add game form for contributors"""
        add_game_container = document["add-game-container"]
        add_game_container.style.display = "block"

    def show_csv_upload_form(self):
        """Show CSV upload form for contributors"""
        upload_container = document["csv-upload-container"]
        upload_container.style.display = "block"
