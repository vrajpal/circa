"""Pydantic schemas for team statistics API responses."""
from datetime import datetime
from pydantic import BaseModel

from app.schemas.schedule import TeamResponse


class TeamStatSnapshotResponse(BaseModel):
    id: int
    team: TeamResponse
    season: int
    week: int
    source: str

    # Offensive
    games_played: int | None
    points_per_game: float | None
    total_yards_per_game: float | None
    passing_yards_per_game: float | None
    rushing_yards_per_game: float | None
    turnovers_per_game: float | None
    red_zone_attempts: int | None
    red_zone_td_pct: float | None
    third_down_pct: float | None

    # Defensive
    points_allowed_per_game: float | None
    yards_allowed_per_game: float | None
    passing_yards_allowed_per_game: float | None
    rushing_yards_allowed_per_game: float | None
    sacks_per_game: float | None
    takeaways_per_game: float | None

    # Situational
    point_differential_per_game: float | None
    fetched_at: datetime

    class Config:
        from_attributes = True


class TeamStandingResponse(BaseModel):
    id: int
    team: TeamResponse
    season: int
    source: str

    wins: int | None
    losses: int | None
    ties: int | None
    win_pct: float | None
    division_rank: int | None
    conference_rank: int | None
    playoff_seed: int | None
    strength_of_schedule: float | None
    home_wins: int | None
    home_losses: int | None
    away_wins: int | None
    away_losses: int | None
    updated_at: datetime

    class Config:
        from_attributes = True


class MatchupComparisonResponse(BaseModel):
    """Side-by-side stat comparison for two teams heading into a matchup."""
    season: int
    week: int

    home_team: TeamResponse
    away_team: TeamResponse

    # Stats for each side — None means we have no data for that team yet
    home_stats: TeamStatSnapshotResponse | None
    away_stats: TeamStatSnapshotResponse | None
    home_standing: TeamStandingResponse | None
    away_standing: TeamStandingResponse | None
