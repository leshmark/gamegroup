"""Pydantic models for game routes"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List


class GameCreate(BaseModel):
    game_id: Optional[int] = None  # For updating existing games by ID
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    owner: Optional[str] = Field(None, min_length=1, max_length=255)
    min_players: Optional[int] = Field(None, ge=1)
    max_players: Optional[int] = Field(None, ge=1)
    description: Optional[str] = None
    short_description: Optional[str] = Field(None, max_length=2000)
    tags: Optional[List[str]] = None
    image_url: Optional[str] = Field(None, max_length=25000)
    bgg_link: Optional[str] = Field(None, max_length=500)
    bgg_rating: Optional[float] = Field(None, ge=0, le=9.9)
    favorited_by: Optional[List[str]] = None

    @model_validator(mode="before")
    def check_validity(cls, values):
        min_players = values.get('min_players')
        max_players = values.get('max_players')
        if min_players is not None and max_players is not None:
            if min_players > max_players:
                raise ValueError("Minimum players cannot be greater than maximum players")
        bgg_rating = values.get('bgg_rating')
        if bgg_rating is not None:
            if bgg_rating < 0 or bgg_rating > 9.9:
                raise ValueError("BGG rating must be between 0 and 9.9")
        return values


class AddGameByBGGLink(BaseModel):
    bgg_url: str = Field(..., description="BoardGameGeek URL for the game")
    owner: str = Field(..., min_length=1, max_length=255, description="Owner of the physical game")


class VoteRequest(BaseModel):
    vote: bool = Field(..., description="Vote value: true to vote, false to remove vote")
