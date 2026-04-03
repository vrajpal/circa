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
    is_opening: Mapped[bool] = mapped_column(Boolean, default=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    game = relationship("Game", back_populates="odds_snapshots")
