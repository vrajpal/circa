from datetime import datetime
from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: int
    abbreviation: str
    name: str
    conference: str
    division: str

    class Config:
        from_attributes = True


class GameResponse(BaseModel):
    id: int
    season: int
    week: int
    home_team: TeamResponse
    away_team: TeamResponse
    game_time: datetime
    slate: str

    class Config:
        from_attributes = True
