from browser import document, ajax, window
import json
import urllib.parse
from config import BASE_URL


class VerifyLinkHandler:
    """Handles authentication link verification"""
    
    def __init__(self):
        """Initialize the VerifyLinkHandler and start verification process"""
        token = self.get_query_param('token')
        if token:
            self.verify_link(token)
        else:
            self.display_message("No token provided in the link.")
    
    def get_query_param(self, param_name):
        """Extract query parameter from URL"""
        query_string = window.location.search
        params = urllib.parse.parse_qs(query_string[1:])  # Skip the '?'
        return params.get(param_name, [None])[-1]
    
    def display_message(self, msg):
        """Display message to user"""
        document["message"].textContent = msg
    
    def verify_link(self, token):
        """Verify the authentication token with the backend"""
        def on_complete(req):
            if req.status == 200:
                response = json.loads(req.text)
                # Store JWT in localStorage for future authenticated requests
                window.localStorage.setItem("auth_token", response["jwt"])
                window.localStorage.setItem("user_email", response["user_email"])
                self.display_message(
                    f"Welcome, {response['user_email']}! You have been successfully authenticated. Closing in 5 seconds..."
                )
                # Wait 5 seconds and then close the window
                window.setTimeout(lambda: window.close(), 5000)
            else:
                self.display_message(
                    "Verification failed. The link may be invalid or expired. Closing in 5 seconds..."
                )
                window.setTimeout(lambda: window.close(), 5000)
        
        req = ajax.Ajax()
        req.bind('complete', on_complete)
        req.open('POST', f'{BASE_URL}/api/v1/auth/action/verify-link', True)
        req.set_header('Content-Type', 'application/json')
        req.send(json.dumps({"token": token}))
