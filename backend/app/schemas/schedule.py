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


class GameResultResponse(BaseModel):
    """Graded outcome for a completed game (straight up / ATS / total)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    game_id: int
    closing_spread_home: float | None
    closing_total: float | None
    su_winner: TeamResponse | None
    ats_winner: TeamResponse | None
    # (home margin) + spread_home. >0 home covered, <0 away covered, ==0 push.
    ats_margin_home: float | None
    # "over" / "under" / "push" relative to the closing total
    total_result: str | None
    graded_at: datetime
