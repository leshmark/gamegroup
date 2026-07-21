"""Pydantic models for game night routes"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class GameNightSessionCreate(BaseModel):
    session_date: datetime = Field(..., description="Date and time of the play session")
    location: Optional[str] = Field(None, max_length=500, description="Location of the play session")
    games_played: List[int] = Field(default_factory=list, description="List of game IDs that were played")
    notes: Optional[str] = Field(None, description="Notes about the play session")


class GameNightCommentCreate(BaseModel):
    comment_text: str = Field(..., min_length=1, max_length=5000, description="Comment text")
    contributor_name: Optional[str] = Field(None, max_length=255, description="Optional display name for guest users")
