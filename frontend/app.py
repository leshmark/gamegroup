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
                # Load users when admin section is shown
                if section_id == "admin" and self.current_user_info and self.current_user_info["authorizations"].get("is_admin"):
                    self.load_users()
                # Show CSV upload form when games section is shown and user is contributor
                if section_id == "games" and self.current_user_info and self.current_user_info["authorizations"].get("is_contributor"):
                    self.show_csv_upload_form()
    
    def handle_navigation(self):
        # self.get_current_user_info()
        logout_container = document.select(".logout-container")
        login_container = document.select(".login-container")
        user_email = window.localStorage.getItem("user_email")
        login_link = document.get(selector="a[href='#login']")
        admin_nav = document.get(selector="#admin_nav")
        admin_nav[0].style.display = "none"
        
        if self.logged_in():
            login_link[0].text = self.current_user_info.get("username", "unknown user")
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
        document["csv-upload-form"].bind("submit", self.handle_csv_upload)
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

    def load_users(self):
        """Fetch and display all users from backend"""
        def on_complete(req):
            users_container = document["users-list-container"]
            if req.status == 200:
                response = json.loads(req.text)
                users = response.get("users", [])
                
                if not users:
                    users_container.innerHTML = "<p>No users found.</p>"
                    return
                
                # Create table
                table_html = """
                <table class="users-table">
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Authorizations</th>
                            <th>Created</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                
                for user in users:
                    # Parse authorizations
                    auth_html = ""
                    if user.get("authorizations"):
                        auths = user["authorizations"].split(",")
                        for auth in auths:
                            auth_class = ""
                            if "admin" in auth.lower():
                                auth_class = "admin"
                            elif "contributor" in auth.lower():
                                auth_class = "contributor"
                            elif "viewer" in auth.lower():
                                auth_class = "viewer"
                            auth_html += f'<span class="user-auth-badge {auth_class}">{auth.strip()}</span>'
                    else:
                        auth_html = '<span style="color: #95a5a6;">None</span>'
                    
                    # Format date
                    created_at = user.get("created_at", "Unknown")
                    if created_at and created_at != "Unknown":
                        # Parse ISO date and format it
                        try:
                            date_parts = created_at.split("T")[0]
                            created_at = date_parts
                        except:
                            pass
                    
                    table_html += f"""
                        <tr>
                            <td>{user.get("username", "")}</td>
                            <td>{user.get("email", "")}</td>
                            <td>{auth_html}</td>
                            <td>{created_at}</td>
                        </tr>
                    """
                
                table_html += """
                    </tbody>
                </table>
                """
                
                users_container.innerHTML = table_html
            elif req.status == 403:
                users_container.innerHTML = "<p style='color: #e74c3c;'>Access denied. Admin privileges required.</p>"
            else:
                users_container.innerHTML = f"<p style='color: #e74c3c;'>Failed to load users. Status: {req.status}</p>"
        
        users_container = document["users-list-container"]
        users_container.innerHTML = "<p>Loading users...</p>"
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('GET', f'{BASE_URL}/admin/users', True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send()

    def show_csv_upload_form(self):
        """Show CSV upload form for contributors"""
        upload_container = document["csv-upload-container"]
        upload_container.style.display = "block"

    def handle_csv_upload(self, event):
        """Handle CSV file upload"""
        event.preventDefault()
        
        file_input = document["csv-file"]
        message_div = document["csv-upload-message"]
        submit_btn = event.target.querySelector(".submit-btn")
        
        if not file_input.files or len(file_input.files) == 0:
            message_div.text = "Please select a CSV file"
            message_div.className = "message error"
            return
        
        file = file_input.files[0]
        
        # Validate file type
        if not file.name.endswith('.csv'):
            message_div.text = "Please select a valid CSV file"
            message_div.className = "message error"
            return
        
        # Disable submit button
        submit_btn.disabled = True
        submit_btn.text = "Uploading..."
        message_div.text = ""
        message_div.className = ""
        
        def on_complete(req):
            submit_btn.disabled = False
            submit_btn.text = "Upload CSV"
            
            if req.status == 200:
                response = json.loads(req.text)
                games_added = response.get("games_added", 0)
                errors = response.get("errors", [])
                
                message_text = f"Successfully added {games_added} game(s)"
                if errors:
                    message_text += f"\n\nErrors encountered:\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        message_text += f"\n... and {len(errors) - 5} more errors"
                
                message_div.text = message_text
                message_div.className = "message success"
                
                # Clear file input
                file_input.value = ""
                
            elif req.status == 403:
                message_div.text = "Access denied. Contributor privileges required."
                message_div.className = "message error"
            else:
                try:
                    error_data = json.loads(req.text)
                    message_div.text = f"Upload failed: {error_data.get('detail', 'Unknown error')}"
                except:
                    message_div.text = f"Upload failed with status {req.status}"
                message_div.className = "message error"
        
        # Create FormData and append file
        from browser import window as win
        FormData = win.FormData.new()
        FormData.append('file', file)
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('POST', f'{BASE_URL}/games/upload-csv', True)
        req.set_header('Authorization', f'Bearer {window.localStorage.getItem("auth_token")}')
        req.send(FormData)

# Initialize the application
app = App()
