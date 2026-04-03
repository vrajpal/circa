from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Pick(Base):
    __tablename__ = "picks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    contest_type: Mapped[str] = mapped_column(String(20))  # millions or survivor
    picked_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", lazy="joined")
    game = relationship("Game", lazy="joined")
    picked_team = relationship("Team", lazy="joined")


class ConsensusPick(Base):
    __tablename__ = "consensus_picks"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    contest_type: Mapped[str] = mapped_column(String(20))
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    picked_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    game = relationship("Game", lazy="joined")
    picked_team = relationship("Team", lazy="joined")
