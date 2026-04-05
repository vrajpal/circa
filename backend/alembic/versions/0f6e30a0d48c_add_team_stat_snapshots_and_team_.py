"""add team_stat_snapshots and team_standings

Revision ID: 0f6e30a0d48c
Revises:
Create Date: 2026-04-04 22:24:14.182875

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f6e30a0d48c'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_stat_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        # Offensive
        sa.Column("games_played", sa.Integer(), nullable=True),
        sa.Column("points_per_game", sa.Float(), nullable=True),
        sa.Column("total_yards_per_game", sa.Float(), nullable=True),
        sa.Column("passing_yards_per_game", sa.Float(), nullable=True),
        sa.Column("rushing_yards_per_game", sa.Float(), nullable=True),
        sa.Column("turnovers_per_game", sa.Float(), nullable=True),
        sa.Column("red_zone_attempts", sa.Integer(), nullable=True),
        sa.Column("red_zone_td_pct", sa.Float(), nullable=True),
        sa.Column("third_down_pct", sa.Float(), nullable=True),
        # Defensive
        sa.Column("points_allowed_per_game", sa.Float(), nullable=True),
        sa.Column("yards_allowed_per_game", sa.Float(), nullable=True),
        sa.Column("passing_yards_allowed_per_game", sa.Float(), nullable=True),
        sa.Column("rushing_yards_allowed_per_game", sa.Float(), nullable=True),
        sa.Column("sacks_per_game", sa.Float(), nullable=True),
        sa.Column("takeaways_per_game", sa.Float(), nullable=True),
        # Situational
        sa.Column("point_differential_per_game", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("team_id", "season", "week", "source", name="uq_team_stat_snapshot"),
    )
    op.create_index("ix_team_stat_snapshots_team_id", "team_stat_snapshots", ["team_id"])
    op.create_index("ix_team_stat_snapshots_season", "team_stat_snapshots", ["season"])
    op.create_index("ix_team_stat_snapshots_week", "team_stat_snapshots", ["week"])
    op.create_index("ix_team_stat_snapshots_fetched_at", "team_stat_snapshots", ["fetched_at"])

    op.create_table(
        "team_standings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=True),
        sa.Column("losses", sa.Integer(), nullable=True),
        sa.Column("ties", sa.Integer(), nullable=True),
        sa.Column("win_pct", sa.Float(), nullable=True),
        sa.Column("division_rank", sa.Integer(), nullable=True),
        sa.Column("conference_rank", sa.Integer(), nullable=True),
        sa.Column("playoff_seed", sa.Integer(), nullable=True),
        sa.Column("strength_of_schedule", sa.Float(), nullable=True),
        sa.Column("home_wins", sa.Integer(), nullable=True),
        sa.Column("home_losses", sa.Integer(), nullable=True),
        sa.Column("away_wins", sa.Integer(), nullable=True),
        sa.Column("away_losses", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("team_id", "season", "source", name="uq_team_standing"),
    )
    op.create_index("ix_team_standings_team_id", "team_standings", ["team_id"])
    op.create_index("ix_team_standings_season", "team_standings", ["season"])


def downgrade() -> None:
    op.drop_table("team_standings")
    op.drop_table("team_stat_snapshots")
