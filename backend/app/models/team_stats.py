"""Models for team-level statistics and standings.

Two tables:
  - TeamStatSnapshot: cumulative per-team stats as of a given week. One row
    per (team, season, week, source). Offensive and defensive numbers that
    accumulate over the season and matter for ATS/survivor decisions.
  - TeamStanding: season-level record and division info. One row per
    (team, season, source), updated in place (upsert pattern).

Design note: all numeric stat columns are nullable so a partial ingest
(e.g. source only has offensive data) doesn't reject the row.
"""
from datetime import datetime

from sqlalchemy import Integer, Float, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TeamStatSnapshot(Base):
    """Cumulative team stats as of a specific week in a season.

    Each row represents what the stats looked like through week N. This lets
    callers query the historical progression — useful for analysing what the
    numbers said heading into a specific matchup.
    """
    __tablename__ = "team_stat_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int] = mapped_column(Integer, index=True)
    # Where the data came from so we can reason about source quality
    source: Mapped[str] = mapped_column(String(50))

    # --- Offensive ---
    games_played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_yards_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    passing_yards_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    rushing_yards_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnovers_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Red zone: attempts and TD% (pct is what bettors actually care about)
    red_zone_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    red_zone_td_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    third_down_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Defensive ---
    points_allowed_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    yards_allowed_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    passing_yards_allowed_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    rushing_yards_allowed_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    sacks_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)
    takeaways_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Situational / overall ---
    # Point differential matters a lot for handicapping. Positive = scoring more than allowing.
    point_differential_per_game: Mapped[float | None] = mapped_column(Float, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    team = relationship("Team", lazy="joined")

    __table_args__ = (
        UniqueConstraint("team_id", "season", "week", "source", name="uq_team_stat_snapshot"),
    )


class TeamStanding(Base):
    """Season-level standing for a team.

    One row per (team, season, source). Updated in place as the season
    progresses rather than storing historical snapshots — callers who need
    historical win totals can derive them from TeamStatSnapshot.games_played.
    """
    __tablename__ = "team_standings"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String(50))

    wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ties: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Win percentage (computed by source, stored for convenience)
    win_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Division rank 1–4
    division_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Conference rank 1–16
    conference_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Playoff seed 1–7, null if not in playoff position
    playoff_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Strength of schedule: average win pct of opponents faced so far.
    # Higher = harder schedule. Useful context for ATS analysis.
    strength_of_schedule: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Home and away records stored as separate W-L pairs for split analysis
    home_wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_losses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_wins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_losses: Mapped[int | None] = mapped_column(Integer, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team = relationship("Team", lazy="joined")

    __table_args__ = (
        UniqueConstraint("team_id", "season", "source", name="uq_team_standing"),
    )
