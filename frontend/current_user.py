from browser import ajax, document, window
import json
from config import BASE_URL


class CurrentUser:
    """Handles fetching current user information"""

    def __init__(self, update_navigation=None):
        """
        Initialize the CurrentUser class

        Args:
            update_navigation: Callback function to call when navigation needs to update
        """
        self.update_navigation = update_navigation
        self.current_user_info = {}
        self.logged_in = False
        self.get_current_user_info()

    def get_current_user_info(self):
        """Fetch current user info from backend"""

        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                self.current_user_info = response
                if self.update_navigation:
                    self.update_navigation()
                print("CurrentUser: ", self.current_user_info)
                self.logged_in = True
                return response
            else:
                print("Failed to fetch user info")
                window.localStorage.removeItem("auth_token")
                window.localStorage.removeItem("user_email")
                self.current_user_info = {}
                self.logged_in = False
                return None

        req = ajax.Ajax()
        req.bind("complete", on_complete)
        req.open("GET", f"{BASE_URL}/api/auth/me", True)
        req.set_header(
            "Authorization", f"Bearer {window.localStorage.getItem('auth_token')}"
        )
        req.send()
