"""Pydantic models for auth routes"""

from pydantic import BaseModel, EmailStr


class AuthRequest(BaseModel):
    email: EmailStr


class VerifyLinkRequest(BaseModel):
    token: str
