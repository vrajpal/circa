"""add moneyline_derived flag to odds_snapshots

Revision ID: 96657e2ad715
Revises: a23521c63c26
Create Date: 2026-06-24 23:43:29.171133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96657e2ad715'
down_revision: Union[str, None] = 'a23521c63c26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate also proposed ADD FOREIGN KEY on picks/consensus_picks and
    # NOT NULL tightening on a couple datetime columns. Those are dropped on
    # purpose: SQLite can't ALTER TABLE ADD a FK (and doesn't enforce FKs by
    # default), and the NOT NULL changes are cosmetic. Only the new column ships.
    op.add_column(
        'odds_snapshots',
        sa.Column('moneyline_derived', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('odds_snapshots', 'moneyline_derived')
