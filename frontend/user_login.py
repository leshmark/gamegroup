from browser import ajax, document, window
import json
from config import BASE_URL

class UserLogin:
    """Handles user login, logout, and user information management"""
    
    def __init__(self, auth_instance, on_navigation_change):
        """
        Initialize the UserLogin class
        
        Args:
            auth_instance: Auth instance for handling login requests
            on_navigation_change: Callback function to call when navigation needs to update
        """
        self.auth = auth_instance
        self.on_navigation_change = on_navigation_change
        self.current_user_info = {}
    
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
        self.current_user_info = {}
        
        # Redirect to home
        window.location.href = "/#home"
        
        # Update navigation
        self.on_navigation_change()
    
    def get_current_user_info(self):
        """Fetch current user info from backend"""
        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                self.current_user_info = response
                self.on_navigation_change()
                self.display_user_info(response)
                return response
            else:
                print("Failed to fetch user info")
                window.localStorage.removeItem("auth_token")
                window.localStorage.removeItem("user_email")
                self.current_user_info = {}
                return None
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('GET', f'{BASE_URL}/auth/me', True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send()

    def display_user_info(self, data):
        """Display user info as nested bulleted list"""
        user_info_div = document["user-info"]
        user_info_div.innerHTML = ""
        
        def create_list(data, parent):
            ul = document.createElement("ul")
            for key, value in data.items():
                li = document.createElement("li")
                if isinstance(value, dict):
                    li.textContent = f"{key}:"
                    create_list(value, li)
                else:
                    li.textContent = f"{key}: {value}"
                ul.appendChild(li)
            parent.appendChild(ul)
        
        create_list(data, user_info_div)
