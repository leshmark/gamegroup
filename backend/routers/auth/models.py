"""Pydantic models for auth routes"""

from pydantic import BaseModel, EmailStr


class AuthRequest(BaseModel):
    email: EmailStr
    one_time_link: bool = True


class VerifyLinkRequest(BaseModel):
    token: str


class SetPINRequest(BaseModel):
    pin: str


class LoginWithPINRequest(BaseModel):
    email: EmailStr
    pin: str
