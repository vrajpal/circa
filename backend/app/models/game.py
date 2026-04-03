from datetime import datetime

from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int] = mapped_column(Integer, index=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    game_time: Mapped[datetime] = mapped_column(DateTime)
    slate: Mapped[str] = mapped_column(String(20), default="regular")  # regular, thanksgiving, christmas, etc.

    home_team = relationship("Team", foreign_keys=[home_team_id], lazy="joined")
    away_team = relationship("Team", foreign_keys=[away_team_id], lazy="joined")
    odds_snapshots = relationship("OddsSnapshot", back_populates="game", lazy="dynamic")
