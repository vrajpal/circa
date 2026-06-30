"""Audit log of ingestion runs.

One row per stage execution (scores, closing-lines, stats, grade, ...). Gives
the pipeline observability: what ran, over what scope, how many rows it wrote,
whether it succeeded. Makes reruns and coverage gaps visible rather than
something you have to infer from the data tables.
"""
from datetime import datetime

from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), index=True)  # e.g. scores, closing_lines, grade
    season: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, success, error
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
