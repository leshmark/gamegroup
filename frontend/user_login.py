from browser import document, window


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
        document["logout-btn"].bind("click", self.handle_logout)

    def handle_login(self, event):
        """Handle login form submission"""
        event.preventDefault()

        email_input = document["email"]
        message_div = document["login-message"]
        submit_btn = document.querySelector(".submit-btn")

        email = email_input.value.strip()

        if not email:
            message_div.text = "Please enter a valid email address"
            message_div.className = "message error"
            return

        # Submit the login request
        self.auth.submit_login_request(email, email_input, message_div, submit_btn)

    def handle_logout(self, event):
        """Handle logout action"""
        event.preventDefault()

        # Clear local storage
        window.localStorage.removeItem("auth_token")
        window.localStorage.removeItem("user_email")

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
                if key == "authorizations" and isinstance(value, dict):
                    li.innerHTML = f"{key.title()}: "
                    # Create badges for each authorization that is True
                    for auth_key, auth_value in value.items():
                        if auth_value:
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

