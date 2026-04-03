from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    abbreviation: Mapped[str] = mapped_column(String(5), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(50))
    conference: Mapped[str] = mapped_column(String(3))  # AFC / NFC
    division: Mapped[str] = mapped_column(String(10))    # North / South / East / West
