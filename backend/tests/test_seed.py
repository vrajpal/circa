"""
Tests for app/seed.py — team seeding script.
"""
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Team
from app.seed import seed_teams, NFL_TEAMS


class TestSeedTeams:
    def _make_engine(self):
        eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=eng)
        return eng

    def test_seeds_all_32_teams(self):
        eng = self._make_engine()
        Session = sessionmaker(bind=eng)
        with patch("app.seed.engine", eng), patch("app.seed.SessionLocal", Session):
            seed_teams()
        session = Session()
        assert session.query(Team).count() == 32
        session.close()

    def test_idempotent_second_run(self, capsys):
        eng = self._make_engine()
        Session = sessionmaker(bind=eng)
        with patch("app.seed.engine", eng), patch("app.seed.SessionLocal", Session):
            seed_teams()
            seed_teams()
        session = Session()
        assert session.query(Team).count() == 32
        session.close()
        captured = capsys.readouterr()
        assert "already seeded" in captured.out.lower()

    def test_nfl_teams_constant_has_32_entries(self):
        assert len(NFL_TEAMS) == 32
