from datetime import datetime

from sqlalchemy import Integer, Float, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    source: Mapped[str] = mapped_column(String(50))  # e.g. pinnacle, bookmaker, draftkings
    spread_home: Mapped[float] = mapped_column(Float, nullable=True)
    total: Mapped[float] = mapped_column(Float, nullable=True)
    moneyline_home: Mapped[int] = mapped_column(Integer, nullable=True)
    moneyline_away: Mapped[int] = mapped_column(Integer, nullable=True)
    # True when the moneyline was *derived* from the spread (a fair, no-vig win
    # probability) rather than sourced from a real book. Lets the UI flag it and
    # keeps us honest about what's a real market price vs a model estimate.
    moneyline_derived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_opening: Mapped[bool] = mapped_column(Boolean, default=False)
    # opening / live / closing. Replaces the implicit "closing == market_consensus"
    # convention with an explicit field that grading and the UI can query directly.
    line_type: Mapped[str] = mapped_column(String(10), default="live", index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    game = relationship("Game", back_populates="odds_snapshots")
