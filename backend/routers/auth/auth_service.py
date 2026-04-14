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
        self.jwt_secret = os.getenv(
            "JWT_PRIVATE_KEY", "your-secret-key-change-in-production"
        )
        self.jwt_algorithm = "HS256"

    def verify_user_exists(self, email: str) -> bool:
        """
        Check if a user with the given email exists in the database

        Args:
            email: User's email address to check

        Returns:
            True if user exists, False otherwise
        """
        results = self.db_service.read_table(
            table_name="users", filter_criteria=[{"col": "email", "op": "=", "val": email}]
        )
        return len(results) > 0

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

    def build_magic_link(
        self, email: str, minutes: int = 15, base_url: str = None, one_time_link: bool = True
    ) -> str:
        """
        Generate token, store it in database, and build the magic link URL

        Args:
            email: User's email address
            minutes: Number of minutes until expiration (default: 15)
            base_url: Base URL to use for the magic link (optional, uses self.base_url if not provided)
            one_time_link: If True, the link is invalidated after first use (default: True)

        Returns:
            Complete magic link URL
        """
        # Generate secure random token
        token = self.generate_auth_token()

        # Set expiration time
        expires_at = self.get_token_expiration(minutes=minutes)

        # Store token in database
        self.store_auth_token(email, token, expires_at, one_time_link=one_time_link)

        # Use provided base_url or fall back to environment variable
        url_base = base_url if base_url else self.base_url

        # Build and return magic link
        return f"{url_base}/auth/action/verify-link?token={token}"

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
        results = self.db_service.read_table(
            table_name="auth_links",
            filter_criteria=[{"col": "token", "op": "=", "val": token}],
            columns=["email", "expires_at", "used", "one_time_link", "created_at"],
        )
        token_data = results[0] if results else None

        if not token_data:
            raise ValueError("Invalid token")

        # Check if token is already used
        if token_data["used"]:
            raise ValueError("Token has already been used")

        # Check if token is expired
        if datetime.now() > token_data["expires_at"] and token_data["one_time_link"]:
            raise ValueError("Token has expired")

        # Mark token as used only if it is one-time or was created more than 24 hours ago
        elapsed = datetime.now() - token_data["created_at"].replace(tzinfo=None)
        if token_data["one_time_link"] or elapsed >= timedelta(hours=24):
            self.mark_token_as_used(token)

        # Generate JWT for frontend
        jwt_token = self.create_jwt(token_data["email"])
        return {"email": token_data["email"], "jwt": jwt_token}

    def store_auth_token(self, email: str, token: str, expires_at: datetime, one_time_link: bool = True):
        """
        Store authentication token in the database

        Args:
            email: User's email address
            token: Generated authentication token
            expires_at: Token expiration timestamp
            one_time_link: If True, the link is invalidated after first use (default: True)
        """
        # Use upsert to insert the new token
        records = [
            (
                {},  # key_fields - empty for insert-only
                {
                    "email": email,
                    "token": token,
                    "expires_at": expires_at,
                    "one_time_link": one_time_link,
                },  # update_fields
            )
        ]

        successful_ids, errors = self.db_service.upsert_records("auth_links", records)

        if errors:
            raise ValueError(f"Failed to store auth token: {errors[0]['error']}")

    def mark_token_as_used(self, token: str):
        """
        Mark authentication token as used

        Args:
            token: Authentication token to mark as used
        """
        # Use upsert to update the token record
        records = [
            (
                {"token": token},  # key_fields - identifies the record
                {"used": True, "used_at": datetime.utcnow()},  # update_fields
            )
        ]

        successful_ids, errors = self.db_service.upsert_records("auth_links", records)

        if errors:
            raise ValueError(f"Failed to mark token as used: {errors[0]['error']}")

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
        results = self.db_service.read_table(
            table_name="users", filter_criteria=[{"col": "email", "op": "=", "val": email}]
        )
        user_data = results[0] if results else None

        payload = {
            "email": email,
            "username": user_data.get("username", ""),
            "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
            "iat": datetime.utcnow(),
        }

        if user_data and "authorizations" in user_data:
            auths = user_data["authorizations"] or ""
            payload["authorizations"] = [k.strip() for k in auths.split(",") if k.strip()]

        print(f"Creating JWT with payload: {payload}\n using secret: {self.jwt_secret}")
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
