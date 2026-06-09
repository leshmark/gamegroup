from browser import document, window
from browser.local_storage import storage


class UserLogin:
    """Handles user login, logout, and user information management"""

    def __init__(self, auth_instance, current_user):
        """
        Initialize the UserLogin class

        Args:
            auth_instance: Auth instance for handling login requests
            on_navigation_change: Callback function to call when navigation needs to update
            current_user: CurrentUser instance for managing user info
        """
        self.auth = auth_instance
        self.current_user = current_user
        document["login-form"].bind("submit", self.handle_login)
        document["pin-login-form"].bind("submit", self.handle_pin_login)
        document["logout-btn"].bind("click", self.handle_logout)
        document["tab-magic-link"].bind("click", self._show_magic_link_tab)
        document["tab-pin"].bind("click", self._show_pin_tab)
        self._restore_remembered_email()

    def _restore_remembered_email(self):
        """Pre-populate email fields from storage if remember_email is set"""
        remembered = storage.get("remember_email", "")
        if remembered:
            document["email"].value = remembered
            document["remember-email"].checked = True
            document["pin-email"].value = remembered

    def handle_login(self, event):
        """Handle login form submission"""
        event.preventDefault()

        email_input = document["email"]
        message_div = document["login-message"]
        submit_btn = document.querySelector("#login-form .submit-btn")

        email = email_input.value.strip()

        if not email:
            message_div.text = "Please enter a valid email address"
            message_div.className = "message error"
            return

        # Save or clear remembered email
        if document["remember-email"].checked:
            storage["remember_email"] = email
        else:
            storage.pop("remember_email", None)

        # Clear any existing auth flows in progress to prevent confusion
        storage.pop("link_verification_semaphore", None)
        storage.pop("auth_token", None)
        storage.pop("user_email", None)
        # Submit the login request
        self.auth.submit_login_request(email, email_input, message_div, submit_btn)

    def handle_pin_login(self, event):
        """Handle PIN login form submission"""
        event.preventDefault()

        email_input = document["pin-email"]
        pin_input = document["pin-input"]
        message_div = document["login-message"]
        submit_btn = document.querySelector("#pin-login-form .submit-btn")

        email = email_input.value.strip()
        pin = pin_input.value.strip()

        if not email:
            message_div.text = "Please enter your email address"
            message_div.className = "message error"
            return

        if not pin:
            message_div.text = "Please enter your PIN"
            message_div.className = "message error"
            return

        # Clear any existing auth flows in progress to prevent confusion
        storage.pop("link_verification_semaphore", None)
        storage.pop("auth_token", None)
        storage.pop("user_email", None)
        self.auth.submit_pin_login_request(email, pin, email_input, pin_input, message_div, submit_btn)

    def _show_magic_link_tab(self, event):
        """Switch to the magic link login tab"""
        document["login-form"].style.display = ""
        document["pin-login-form"].style.display = "none"
        document["tab-magic-link"].className = "login-tab active"
        document["tab-pin"].className = "login-tab"
        document["login-message"].text = ""
        document["login-message"].className = "message"

    def _show_pin_tab(self, event):
        """Switch to the PIN login tab"""
        document["login-form"].style.display = "none"
        document["pin-login-form"].style.display = ""
        document["tab-magic-link"].className = "login-tab"
        document["tab-pin"].className = "login-tab active"
        document["login-message"].text = ""
        document["login-message"].className = "message"

    def handle_logout(self, event):
        """Handle logout action"""
        event.preventDefault()

        # Clear local storage
        storage.pop("auth_token", None)
        storage.pop("user_email", None)

        # Clear current user info
        self.current_user.current_user_info = {}

        # Redirect to home
        window.location.href = "/#home"

    def display_user_info(self, data):
        """Display user info with styled authorization badges"""
        user_info_div = document["user-info"]
        user_info_div.innerHTML = ""

        def create_list(data, parent):
            ul = document.createElement("ul")
            for key, value in data.items():
                li = document.createElement("li")

                # Special handling for authorizations
                if key == "authorizations" and isinstance(value, list):
                    li.innerHTML = f"{key.title()}: "
                    # Create badges for each authorization level
                    for auth_key in value:
                        # Determine badge class based on authorization type
                        auth_class = ""
                        if "admin" in auth_key.lower():
                            auth_class = "admin"
                        elif "contributor" in auth_key.lower():
                            auth_class = "contributor"
                        elif "viewer" in auth_key.lower():
                            auth_class = "viewer"

                        badge = document.createElement("span")
                        badge.className = f"user-auth-badge {auth_class}"
                        badge.textContent = auth_key
                        li.appendChild(badge)
                elif isinstance(value, dict):
                    li.textContent = ""
                    li.textContent = f"{key.title()}:"

                    create_list(value, li)
                else:
                    li.textContent = f"{key.title()}: {value}"
                ul.appendChild(li)
            parent.appendChild(ul)

        create_list(data, user_info_div)
