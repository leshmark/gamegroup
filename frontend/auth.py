from browser import document, ajax, window
import json
from config import BASE_URL


class Auth:
    """Handle authentication requests and responses"""
    
    def __init__(self):
        """Initialize the Auth handler"""
        self.button_default_text = "Send Login Link"
    
    def submit_login_request(self, email, email_input, message_div, submit_btn):
        """Submit login request to the backend"""
        
        # Disable button during request
        submit_btn.disabled = True
        submit_btn.text = "Sending..."
        message_div.text = ""
        message_div.className = "message"
        
        def on_complete(req):
            """Handle successful response"""
            self._handle_login_response(req, email, email_input, message_div, submit_btn)
        
        def on_error(req):
            """Handle request error"""
            self._handle_login_error(req, message_div, submit_btn)
        
        # Send POST request
        req = ajax.ajax()
        req.bind('complete', on_complete)
        req.bind('error', on_error)
        req.open('POST', f'{BASE_URL}/auth/request-link', True)
        req.set_header('Content-Type', 'application/json')
        req.send(json.dumps({"email": email}))
    
    def _handle_login_response(self, req, email, email_input, message_div, submit_btn):
        """Handle successful login response"""
        submit_btn.disabled = False
        submit_btn.text = self.button_default_text
        
        if req.status == 200:
            message_div.text = "Check your email! We've sent you a login link."
            message_div.className = "message success"
            # Store email for profile display
            window.localStorage.setItem("user_email", email)
            email_input.value = ""
        else:
            try:
                error_data = json.loads(req.text)
                error_msg = error_data.get("detail", "An error occurred")
            except:
                error_msg = "Failed to send login link. Please try again."
            message_div.text = error_msg
            message_div.className = "message error"
    
    def _handle_login_error(self, req, message_div, submit_btn):
        """Handle request error"""
        submit_btn.disabled = False
        submit_btn.text = self.button_default_text
        message_div.text = "Network error. Please check your connection and try again."
        message_div.className = "message error"
