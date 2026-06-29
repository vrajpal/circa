"""add grading, results, line_type, team ATS/OU form, ingestion runs

Revision ID: a23521c63c26
Revises: e09a30e3d9e5
Create Date: 2026-06-24 23:30:56.243285

Notes
-----
* New tables: game_results (graded outcome per game) and ingestion_runs
  (pipeline audit log).
* odds_snapshots.line_type makes opening/live/closing explicit. Existing rows
  are backfilled: is_opening -> 'opening', source 'market_consensus' -> 'closing',
  everything else stays 'live'.
* picks / consensus_picks gain grading columns (result, graded_against_snapshot_id,
  graded_at). graded_against_snapshot_id is a plain integer column: SQLite cannot
  ALTER TABLE ADD a FOREIGN KEY to an existing table, and doesn't enforce FKs by
  default anyway. The ORM models still declare the relationship.
* team_standings gains ATS and O/U record columns, populated by the grading stage.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a23521c63c26'
down_revision: Union[str, None] = 'e09a30e3d9e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New tables -------------------------------------------------------
    op.create_table(
        'game_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id'), nullable=False),
        sa.Column('graded_against_snapshot_id', sa.Integer(),
                  sa.ForeignKey('odds_snapshots.id'), nullable=True),
        sa.Column('closing_spread_home', sa.Float(), nullable=True),
        sa.Column('closing_total', sa.Float(), nullable=True),
        sa.Column('su_winner_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('ats_winner_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True),
        sa.Column('ats_margin_home', sa.Float(), nullable=True),
        sa.Column('total_result', sa.String(length=5), nullable=True),
        sa.Column('graded_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_game_results_game_id'), 'game_results', ['game_id'], unique=True)

    op.create_table(
        'ingestion_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('season', sa.Integer(), nullable=True),
        sa.Column('week', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='running'),
        sa.Column('rows_written', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )
    op.create_index(op.f('ix_ingestion_runs_source'), 'ingestion_runs', ['source'])
    op.create_index(op.f('ix_ingestion_runs_season'), 'ingestion_runs', ['season'])

    # --- odds_snapshots.line_type ----------------------------------------
    op.add_column('odds_snapshots',
                  sa.Column('line_type', sa.String(length=10), nullable=False, server_default='live'))
    op.create_index(op.f('ix_odds_snapshots_line_type'), 'odds_snapshots', ['line_type'], unique=False)
    op.execute("UPDATE odds_snapshots SET line_type = 'opening' WHERE is_opening = 1")
    op.execute("UPDATE odds_snapshots SET line_type = 'closing' WHERE source = 'market_consensus'")

    # --- pick grading columns --------------------------------------------
    for tbl in ('picks', 'consensus_picks'):
        op.add_column(tbl, sa.Column('result', sa.String(length=10), nullable=False,
                                     server_default='pending'))
        op.add_column(tbl, sa.Column('graded_against_snapshot_id', sa.Integer(), nullable=True))
        op.add_column(tbl, sa.Column('graded_at', sa.DateTime(), nullable=True))

    # --- team_standings ATS / O/U records --------------------------------
    for col in ('ats_wins', 'ats_losses', 'ats_pushes', 'ou_overs', 'ou_unders', 'ou_pushes'):
        op.add_column('team_standings', sa.Column(col, sa.Integer(), nullable=True))


def downgrade() -> None:
    for col in ('ou_pushes', 'ou_unders', 'ou_overs', 'ats_pushes', 'ats_losses', 'ats_wins'):
        op.drop_column('team_standings', col)
    for tbl in ('consensus_picks', 'picks'):
        op.drop_column(tbl, 'graded_at')
        op.drop_column(tbl, 'graded_against_snapshot_id')
        op.drop_column(tbl, 'result')
    op.drop_index(op.f('ix_odds_snapshots_line_type'), table_name='odds_snapshots')
    op.drop_column('odds_snapshots', 'line_type')
    op.drop_index(op.f('ix_ingestion_runs_season'), table_name='ingestion_runs')
    op.drop_index(op.f('ix_ingestion_runs_source'), table_name='ingestion_runs')
    op.drop_table('ingestion_runs')
    op.drop_index(op.f('ix_game_results_game_id'), table_name='game_results')
    op.drop_table('game_results')
