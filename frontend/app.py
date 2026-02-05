from browser import ajax, document, window
from auth import Auth
import json
from config import BASE_URL

class App:
    """Main application class for managing navigation and authentication"""
    
    def __init__(self):
        """Initialize the application and bind event handlers"""
        self.current_user_info = {}
        self.get_current_user_info()
        self.auth = Auth()
        self.bind_events()
        self.handle_navigation()
    
    def show_section(self, section_id):
        """Show the specified section and hide all others"""
        sections = document.select(".content-section")
        for section in sections:
            section.style.display = "none"
        
        if section_id:
            target = document.get(selector=f"#{section_id}")
            if target:
                target[0].style.display = "block"
    
    def handle_navigation(self):
        # self.get_current_user_info()
        logout_container = document.select(".logout-container")
        login_container = document.select(".login-container")
        user_email = window.localStorage.getItem("user_email")
        login_link = document.get(selector="a[href='#login']")
        admin_nav = document.get(selector="#admin_nav")
        admin_nav[0].style.display = "none"
        
        if self.logged_in():
            login_link[0].text = user_email
            logout_container[0].style.display = "block"
            login_container[0].style.display = "none"
            if self.current_user_info and self.current_user_info["authorizations"].get("is_admin"):
                admin_nav[0].style.display = "block"
        else:
            login_link[0].text = "Login"
            logout_container[0].style.display = "none"
            login_container[0].style.display = "block"
            admin_nav[0].style.display = "none"

        """Handle URL hash changes for navigation"""
        hash_value = window.location.hash[1:]  # Remove the # symbol
        self.show_section(hash_value)
    
    def logged_in(self):
        """Check if the user is logged in by verifying the presence of a JWT token"""
        token = window.localStorage.getItem("auth_token") or None
        return token is not None
    
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
        
        # Redirect to home
        window.location.href = "/#home"
        
        # Update navigation
        self.handle_navigation()
    
    def bind_events(self):
        """Bind all event handlers"""
        document["login-form"].bind("submit", self.handle_login)
        document["logout-btn"].bind("click", self.handle_logout)
        window.bind("hashchange", lambda e: self.handle_navigation())

    def get_current_user_info(self):
        """Fetch current user info from backend"""
        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                self.current_user_info = response
                self.handle_navigation()
                #under document["user-info"] add user info as bulleted list with indentation for sub-items recursively
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
                create_list(response, user_info_div)
                return response
            else:
                print("Failed to fetch user info")
                self.current_user_info = {}
                return None
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('GET', f'{BASE_URL}/auth/me', True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send()

# Initialize the application
app = App()
