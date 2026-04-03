from datetime import datetime
from pydantic import BaseModel

from app.schemas.schedule import TeamResponse, GameResponse
from app.schemas.auth import UserResponse


class PickCreate(BaseModel):
    game_id: int
    picked_team_id: int
    contest_type: str  # millions or survivor
    comment: str | None = None


class PickResponse(BaseModel):
    id: int
    user: UserResponse
    game: GameResponse
    season: int
    week: int
    contest_type: str
    picked_team: TeamResponse
    comment: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ConsensusPickCreate(BaseModel):
    game_id: int | None = None
    picked_team_id: int
    contest_type: str


class ConsensusPickResponse(BaseModel):
    id: int
    season: int
    week: int
    contest_type: str
    game: GameResponse | None
    picked_team: TeamResponse
    decided_at: datetime

    class Config:
        from_attributes = True


class SlateWarning(BaseModel):
    message: str
    slate: str
    remaining_teams: list[TeamResponse]
