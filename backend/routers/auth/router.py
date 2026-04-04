"""Authentication routes for user login and verification"""

from fastapi import APIRouter, HTTPException, Depends, Request
import logging

from .models import AuthRequest, VerifyLinkRequest
from .auth_service import AuthService
from .email_service import EmailService
from auth_dependencies import AuthDependencies
from database_service import DatabaseService

logger = logging.getLogger(__name__)


class AuthRouter:
    def __init__(self):
        self.db_service = DatabaseService()
        self.auth_service = AuthService(self.db_service)
        self.email_service = EmailService()
        self.auth_dependencies = AuthDependencies()
        self.router = self._build_router()

    def _build_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
        get_current_user = self.auth_dependencies._get_current_user_dependency()

        @router.get("/me")
        def get_current_user_info(current_user: dict = Depends(get_current_user)):
            """Get current authenticated user information from JWT token, including their authorizations"""
            return self._get_current_user_info(current_user)

        @router.post("/action/request-link")
        def request_auth_link(auth_request: AuthRequest, request: Request):
            """Request a one-time authentication link via email"""
            return self._request_auth_link(auth_request, request)

        @router.post("/action/verify-link")
        def verify_auth_link(verify_request: VerifyLinkRequest):
            """Verify the one-time authentication link"""
            return self._verify_auth_link(verify_request)

        return router

    def _get_current_user_info(self, current_user: dict):
        try:
            return {
                "email": current_user["email"],
                "username": current_user.get("username", ""),
                "authorizations": current_user.get("authorizations", []),
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to retrieve user info: {str(e)}"
            )

    def _request_auth_link(self, auth_request: AuthRequest, request: Request):
        email = auth_request.email

        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        forwarded_host = request.headers.get("x-forwarded-host", request.url.hostname)
        forwarded_port = request.headers.get("x-forwarded-port")
        if forwarded_host and forwarded_host in ("localhost", "127.0.0.1"):
            forwarded_host = request.url.hostname
            forwarded_port = 8443
            base_url = f"{forwarded_proto}://{forwarded_host}:{forwarded_port}"
        else:
            base_url = f"{forwarded_proto}://{forwarded_host}"
        logger.info(f"Extracted base_url: {base_url}")

        send_link = True
        try:
            if self.auth_service.verify_user_exists(email):
                magic_link = self.auth_service.build_magic_link(
                    email, minutes=15, base_url=base_url, one_time_link=auth_request.one_time_link
                )
            else:
                logger.warning(f"Authentication requested for non-existent email: {email}")
                send_link = False
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Magic Link generation error: {str(e)}")

        try:
            if send_link and auth_request.one_time_link:
                self.email_service.send_auth_email(email, magic_link)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send authentication email: {str(e)}")

        return {
            "message": "Authentication link sent to your email",
            "magic_link": magic_link if send_link else None,
        }

    def _verify_auth_link(self, verify_request: VerifyLinkRequest):
        try:
            result = self.auth_service.verify_token(verify_request.token)
            return {
                "message": "Authentication successful",
                "user_email": result["email"],
                "jwt": result["jwt"],
            }
        except ValueError as e:
            logger.warning(f"Token verification failed - invalid token: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))


_handler = AuthRouter()
router = _handler.router
