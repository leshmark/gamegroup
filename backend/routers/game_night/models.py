"""Pydantic models for game night routes"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class GameNightSessionCreate(BaseModel):
    session_date: datetime = Field(..., description="Date and time of the play session")
    location: Optional[str] = Field(None, max_length=500, description="Location of the play session")
    games_played: List[int] = Field(default_factory=list, description="List of game IDs that were played")
    notes: Optional[str] = Field(None, description="Notes about the play session")
