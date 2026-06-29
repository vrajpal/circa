"""create base tables (users, teams, games, odds_snapshots, picks, consensus_picks)

Revision ID: d1e2f3a4b5c6
Revises:
Create Date: 2026-06-24 23:55:00.000000

These core tables historically existed only because app startup called
Base.metadata.create_all — no migration ever created them, so the Alembic
chain started from 0f6e30a0d48c (which adds team_stat_snapshots and references
teams.id). Once create_all was removed in favour of Alembic owning the schema,
a from-scratch `alembic upgrade head` had nothing to create these tables. This
migration backfills that gap and becomes the new root of the chain.

Tables are created in their ORIGINAL shape. Later migrations layer on top:
  e09a30e3d9e5 -> games.score_home/away
  a23521c63c26 -> game_results, ingestion_runs, odds line_type, pick grading, ATS/OU
  96657e2ad715 -> odds_snapshots.moneyline_derived
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(50), nullable=False, unique=True),
        sa.Column('email', sa.String(120), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    op.create_table(
        'teams',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('abbreviation', sa.String(5), nullable=False, unique=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('conference', sa.String(3), nullable=False),
        sa.Column('division', sa.String(10), nullable=False),
    )
    op.create_index(op.f('ix_teams_abbreviation'), 'teams', ['abbreviation'], unique=True)

    op.create_table(
        'games',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('home_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('away_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('game_time', sa.DateTime(), nullable=False),
        sa.Column('slate', sa.String(20), nullable=True),
    )
    op.create_index(op.f('ix_games_season'), 'games', ['season'])
    op.create_index(op.f('ix_games_week'), 'games', ['week'])

    op.create_table(
        'odds_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id'), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('spread_home', sa.Float(), nullable=True),
        sa.Column('total', sa.Float(), nullable=True),
        sa.Column('moneyline_home', sa.Integer(), nullable=True),
        sa.Column('moneyline_away', sa.Integer(), nullable=True),
        sa.Column('is_opening', sa.Boolean(), nullable=True),
        sa.Column('captured_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_odds_snapshots_game_id'), 'odds_snapshots', ['game_id'])
    op.create_index(op.f('ix_odds_snapshots_captured_at'), 'odds_snapshots', ['captured_at'])

    op.create_table(
        'picks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id'), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('contest_type', sa.String(20), nullable=False),
        sa.Column('picked_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_picks_user_id'), 'picks', ['user_id'])

    op.create_table(
        'consensus_picks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('week', sa.Integer(), nullable=False),
        sa.Column('contest_type', sa.String(20), nullable=False),
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id'), nullable=True),
        sa.Column('picked_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('consensus_picks')
    op.drop_index(op.f('ix_picks_user_id'), table_name='picks')
    op.drop_table('picks')
    op.drop_index(op.f('ix_odds_snapshots_captured_at'), table_name='odds_snapshots')
    op.drop_index(op.f('ix_odds_snapshots_game_id'), table_name='odds_snapshots')
    op.drop_table('odds_snapshots')
    op.drop_index(op.f('ix_games_week'), table_name='games')
    op.drop_index(op.f('ix_games_season'), table_name='games')
    op.drop_table('games')
    op.drop_index(op.f('ix_teams_abbreviation'), table_name='teams')
    op.drop_table('teams')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
