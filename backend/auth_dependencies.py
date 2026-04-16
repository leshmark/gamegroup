from fastapi import Depends, HTTPException, Header
from typing import Optional
import jwt
import os


class AuthDependencies:
    """Class to handle authentication dependencies for FastAPI endpoints"""

    def __init__(self):
        self.jwt_secret = os.getenv("JWT_PRIVATE_KEY")
        self.jwt_algorithm = "HS256"

    def verify_jwt_token(self, token: str) -> dict:
        """
        Verify JWT token and extract user information

        Args:
            token: JWT token string

        Returns:
            Dictionary containing user information from token

        Raises:
            HTTPException: If token is invalid or expired
        """
        if not self.jwt_secret:
            print("JWT secret not configured")
            raise HTTPException(status_code=500, detail="JWT secret not configured")

        try:
            print(f"Verifying JWT token: {token} with secret: {self.jwt_secret}")
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )
            print(f"Decoded JWT payload: {payload}")
            return payload
        except jwt.ExpiredSignatureError:
            print("JWT token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            print("Invalid JWT token")
            raise HTTPException(status_code=401, detail="Invalid token")

    def get_current_user(self, authorization: Optional[str] = Header(None)):
        """Dependency to verify user is authenticated"""
        if not authorization:
            raise HTTPException(status_code=401, detail="Not authenticated")

        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")

        token = authorization.replace("Bearer ", "")
        print(f"Received token: {token}")
        user = self.verify_jwt_token(token)

        if "email" not in user:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        return user

    def _get_current_user_dependency(self):
        """Helper to create a dependency for get_current_user"""

        def dependency(authorization: Optional[str] = Header(None)):
            # output to log the provided authorization header
            print(f"Authorization header: {authorization}")
            return self.get_current_user(authorization)

        return dependency

    def require_contributor(self, current_user: dict):
        """Dependency to verify user has contributor access"""
        authorizations = current_user.get("authorizations", [])
        if "is_contributor" not in authorizations and "is_admin" not in authorizations:
            raise HTTPException(status_code=403, detail="Contributor access required")
        return current_user

    def _get_require_contributor_dependency(self):
        """Helper to create a dependency for require_contributor"""

        def dependency(
            current_user: dict = Depends(self._get_current_user_dependency()),
        ):
            return self.require_contributor(current_user)

        return dependency

    def require_admin(self, current_user: dict):
        """Dependency to verify user has admin access"""
        if "is_admin" not in current_user.get("authorizations", []):
            raise HTTPException(status_code=403, detail="Admin access required")
        return current_user

    def _get_require_admin_dependency(self):
        """Helper to create a dependency for require_admin"""

        def dependency(
            current_user: dict = Depends(self._get_current_user_dependency()),
        ):
            return self.require_admin(current_user)

        return dependency

    def require_viewer(self, current_user: dict):
        """Dependency to verify user has viewer access"""
        authorizations = current_user.get("authorizations", [])
        if not any(
            r in authorizations for r in ("is_viewer", "is_contributor", "is_admin")
        ):
            raise HTTPException(status_code=403, detail="Viewer access required")
        return current_user

    def _get_require_viewer_dependency(self):
        """Helper to create a dependency for require_viewer"""

        def dependency(
            current_user: dict = Depends(self._get_current_user_dependency()),
        ):
            return self.require_viewer(current_user)

        return dependency
