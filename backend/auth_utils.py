import os
import secrets
from datetime import datetime, timedelta
import jwt


class AuthService:
    """Service for handling authentication token generation and management"""
    
    def __init__(self, db_service):
        """
        Initialize auth service with configuration from environment variables
        
        Args:
            db_service: DatabaseService instance for storing tokens
        """
        self.base_url = os.getenv("BASE_URL", "http://localhost:8080")
        self.db_service = db_service
        self.jwt_secret = os.getenv("JWT_PRIVATE_KEY", "your-secret-key-change-in-production")
        self.jwt_algorithm = "HS256"
    
    def generate_auth_token(self) -> str:
        """Generate a secure random authentication token"""
        return secrets.token_urlsafe(32)
    
    def get_token_expiration(self, minutes: int = 15) -> datetime:
        """
        Calculate token expiration timestamp
        
        Args:
            minutes: Number of minutes until expiration (default: 15)
        
        Returns:
            Expiration timestamp
        """
        return datetime.now() + timedelta(minutes=minutes)
    
    def build_magic_link(self, email: str, minutes: int = 15) -> str:
        """
        Generate token, store it in database, and build the magic link URL
        
        Args:
            email: User's email address
            minutes: Number of minutes until expiration (default: 15)
        
        Returns:
            Complete magic link URL
        """
        # Generate secure random token
        token = self.generate_auth_token()
        
        # Set expiration time
        expires_at = self.get_token_expiration(minutes=minutes)
        
        # Store token in database
        self.db_service.store_auth_token(email, token, expires_at)
        
        # Build and return magic link
        return f"{self.base_url}/auth/verify-link?token={token}"
    
    def verify_token(self, token: str) -> dict:
        """
        Verify authentication token and mark it as used
        
        Args:
            token: Authentication token to verify
        
        Returns:
            Dictionary with email if valid
        
        Raises:
            ValueError: If token is invalid, expired, or already used
        """
        # Retrieve token from database
        token_data = self.db_service.get_auth_token(token)
        
        if not token_data:
            raise ValueError("Invalid token")
        
        # Check if token is already used
        if token_data["used"]:
            raise ValueError("Token has already been used")
        
        # Check if token is expired
        if datetime.now() > token_data["expires_at"]:
            raise ValueError("Token has expired")
        
        # Mark token as used
        self.db_service.mark_token_as_used(token)
        
        # Generate JWT for frontend
        jwt_token = self.create_jwt(token_data["email"])
        return {"email": token_data["email"], "jwt": jwt_token}
    
    def create_jwt(self, email: str, expires_in_hours: int = 24) -> str:
        """
        Create a JWT token for authenticated user
        
        Args:
            email: User's email address
            expires_in_hours: Number of hours until JWT expiration (default: 24)
        
        Returns:
            Encoded JWT token string
        """
        # read from users table and add roles/permissions to JWT if needed
        user_data = self.db_service.get_user_by_email(email)

        payload = {
            "email": email,
            "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
            "iat": datetime.utcnow()
        }

        if user_data and "authorizations" in user_data:
            for key in user_data["authorizations"].split(","):
                payload[key.strip()] = True

        print(f"Creating JWT with payload: {payload}\n using secret: {self.jwt_secret}")
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def verify_jwt(self, token: str) -> dict:
        """
        Verify and decode a JWT token
        
        Args:
            token: JWT token string to verify
        
        Returns:
            Decoded payload containing user information
        
        Raises:
            jwt.ExpiredSignatureError: If token has expired
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid token")
