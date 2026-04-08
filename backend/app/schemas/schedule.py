from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    abbreviation: str
    name: str
    conference: str
    division: str


class GameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    week: int
    home_team: TeamResponse
    away_team: TeamResponse
    game_time: datetime
    slate: str
    score_home: int | None = None
    score_away: int | None = None
