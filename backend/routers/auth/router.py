"""Authentication routes for user login and verification"""

from fastapi import APIRouter, HTTPException, Depends, Request
import logging

from .models import AuthRequest, VerifyLinkRequest
from .auth_utils import AuthService
from .email_utils import EmailService
from auth_dependencies import AuthDependencies
from db_utils import DatabaseService

logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()
auth_service = AuthService(db_service)
email_service = EmailService()
auth_dependencies = AuthDependencies()

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me")
def get_current_user_info(
    current_user: dict = Depends(auth_dependencies._get_current_user_dependency()),
):
    """Get current authenticated user information from JWT token, including their authorizations"""
    try:
        return {
            "email": current_user["email"],
            "username": current_user.get("username", ""),
            "authorizations": {
                key: current_user[key] for key in current_user if key.startswith("is_")
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve user info: {str(e)}"
        )


@router.post("/action/request-link")
def request_auth_link(auth_request: AuthRequest, request: Request):
    """Request a one-time authentication link via email"""
    email = auth_request.email

    # Extract base URL from X-Forwarded headers if present, else fallback to request.url
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    forwarded_host = request.headers.get("x-forwarded-host", request.url.hostname)
    forwarded_port = request.headers.get("x-forwarded-port")
    if forwarded_host and forwarded_host in ("localhost", "127.0.0.1"):
        # If host is localhost, use the request URL's host and port to ensure it works in local development
        forwarded_host = request.url.hostname
        forwarded_port = 8443
        base_url = f"{forwarded_proto}://{forwarded_host}:{forwarded_port}"
    else:
        base_url = f"{forwarded_proto}://{forwarded_host}"
    logger.info(f"Extracted base_url: {base_url}")

    send_link = True  # Flag to determine whether to send the email (set to False if user doesn't exist, but still generate a link for security)
    # Generate token, store it, and build magic link
    try:
        if auth_service.verify_user_exists(email):
            magic_link = auth_service.build_magic_link(
                email, minutes=15, base_url=base_url, one_time_link=auth_request.one_time_link
            )
        else:
            # For security, we can still generate a magic link even if the user doesn't exist, but it won't be valid. This prevents user enumeration attacks.
            logger.warning(f"Authentication requested for non-existent email: {email}")
            send_link = False
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Magic Link generation error: {str(e)}")

    # Send email
    try:
        # Only send the email if the user exists and it's not a one-time link
        if send_link and not auth_request.one_time_link:
            email_service.send_auth_email(email, magic_link)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send authentication email: {str(e)}")

    return {
        "message": "Authentication link sent to your email",
        "magic_link": magic_link if send_link else None,
    }


@router.post("/action/verify-link")
def verify_auth_link(verify_request: VerifyLinkRequest):
    """Verify the one-time authentication link"""
    try:
        result = auth_service.verify_token(verify_request.token)
        return {
            "message": "Authentication successful",
            "user_email": result["email"],
            "jwt": result["jwt"],
        }
    except ValueError as e:
        logger.warning(f"Token verification failed - invalid token: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
