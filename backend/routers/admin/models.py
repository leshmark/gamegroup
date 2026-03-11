"""Pydantic models for admin routes"""

from pydantic import BaseModel, EmailStr, Field


class UserUpsert(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=1, max_length=255)
    is_viewer: bool = False
    is_contributor: bool = False
    is_admin: bool = False
