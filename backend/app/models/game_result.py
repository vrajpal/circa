"""Graded outcome for a completed game.

One row per game (one-to-one with Game), written by the grading stage once a
game has a final score AND a real closing line. Storing the result rather than
recomputing it on every query keeps pick-grading and the consensus page cheap,
and pins down exactly which line snapshot the grade was computed against.

Grading is always done against the *real* closing line (source
"market_consensus" from covers.com) — never the synthetic line-movement
snapshots, which exist only to exercise the line-history UI.
"""
from datetime import datetime

from sqlalchemy import Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GameResult(Base):
    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), unique=True, index=True)

    # Provenance: the closing-line snapshot this grade was computed against.
    graded_against_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("odds_snapshots.id"), nullable=True
    )
    # The actual line values, snapshotted here so a later odds re-ingest can't
    # silently change what we graded on.
    closing_spread_home: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_total: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Straight up ---
    # Winner of the game outright. NULL on a tie.
    su_winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)

    # --- Against the spread ---
    # Team that covered the closing spread. NULL on a push (or no line).
    ats_winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    # (home margin) + spread_home. >0 home covered, <0 away covered, ==0 push.
    ats_margin_home: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Total ---
    # "over" / "under" / "push" relative to the closing total. NULL if no total.
    total_result: Mapped[str | None] = mapped_column(String(5), nullable=True)

    graded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    game = relationship("Game", back_populates="result", lazy="joined")
    su_winner = relationship("Team", foreign_keys=[su_winner_team_id], lazy="joined")
    ats_winner = relationship("Team", foreign_keys=[ats_winner_team_id], lazy="joined")
