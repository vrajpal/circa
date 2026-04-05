"""
Unit tests for SQLAlchemy models.

Verifies that models persist correctly to the in-memory database,
constraints are enforced, and relationships resolve without errors.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User, Team, Game, OddsSnapshot, Pick, ConsensusPick
from app.services.auth import hash_password


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

class TestUserModel:
    def test_create_user(self, db_session):
        u = User(username="charlie", email="charlie@test.com", password_hash=hash_password("pw"))
        db_session.add(u)
        db_session.flush()
        assert u.id is not None
        assert u.created_at is not None

    def test_username_unique(self, db_session):
        u1 = User(username="dup", email="a@test.com", password_hash="h")
        u2 = User(username="dup", email="b@test.com", password_hash="h")
        db_session.add_all([u1, u2])
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_email_unique(self, db_session):
        u1 = User(username="u1", email="same@test.com", password_hash="h")
        u2 = User(username="u2", email="same@test.com", password_hash="h")
        db_session.add_all([u1, u2])
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_query_by_username(self, db_session, user_alice):
        result = db_session.query(User).filter(User.username == "alice").first()
        assert result is not None
        assert result.id == user_alice.id


# ---------------------------------------------------------------------------
# Team model
# ---------------------------------------------------------------------------

class TestTeamModel:
    def test_create_team(self, db_session):
        t = Team(abbreviation="TST", name="Test Team", conference="AFC", division="North")
        db_session.add(t)
        db_session.flush()
        assert t.id is not None

    def test_abbreviation_unique(self, db_session):
        t1 = Team(abbreviation="XX", name="X One", conference="AFC", division="East")
        t2 = Team(abbreviation="XX", name="X Two", conference="NFC", division="West")
        db_session.add_all([t1, t2])
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_query_by_abbreviation(self, db_session, teams):
        result = db_session.query(Team).filter(Team.abbreviation == "KC").first()
        assert result is not None
        assert result.name == "Kansas City Chiefs"

    def test_team_count_matches_fixture(self, db_session, teams):
        assert db_session.query(Team).count() == len(teams)


# ---------------------------------------------------------------------------
# Game model
# ---------------------------------------------------------------------------

class TestGameModel:
    def test_create_game(self, db_session, teams):
        kc  = teams["KC"]
        buf = teams["BUF"]
        g = Game(
            season=2025, week=1,
            home_team_id=kc.id, away_team_id=buf.id,
            game_time=datetime(2025, 9, 7, 13, 0, 0),
            slate="regular",
        )
        db_session.add(g)
        db_session.flush()
        assert g.id is not None
        assert g.slate == "regular"

    def test_game_team_relationships(self, db_session, sample_games, teams):
        g = sample_games[0]
        assert g.home_team.abbreviation == "KC"
        assert g.away_team.abbreviation == "BUF"

    def test_game_default_slate(self, db_session, teams):
        g = Game(
            season=2025, week=5,
            home_team_id=teams["SF"].id, away_team_id=teams["DAL"].id,
            game_time=datetime(2025, 10, 12, 13, 0),
        )
        db_session.add(g)
        db_session.flush()
        assert g.slate == "regular"

    def test_filter_by_week(self, db_session, sample_games):
        wk1 = db_session.query(Game).filter(Game.week == 1).all()
        assert len(wk1) == 2

    def test_filter_by_slate(self, db_session, sample_games):
        tg = db_session.query(Game).filter(Game.slate == "thanksgiving").all()
        assert len(tg) == 3


# ---------------------------------------------------------------------------
# OddsSnapshot model
# ---------------------------------------------------------------------------

class TestOddsSnapshotModel:
    def test_create_snapshot(self, db_session, sample_games):
        snap = OddsSnapshot(
            game_id=sample_games[0].id, source="pinnacle",
            spread_home=-3.0, total=52.5,
            moneyline_home=-165, moneyline_away=140,
            is_opening=True, captured_at=datetime(2025, 9, 1),
        )
        db_session.add(snap)
        db_session.flush()
        assert snap.id is not None

    def test_nullable_fields_can_be_none(self, db_session, sample_games):
        snap = OddsSnapshot(
            game_id=sample_games[0].id, source="manual",
            spread_home=None, total=None,
            moneyline_home=None, moneyline_away=None,
            is_opening=False, captured_at=datetime(2025, 9, 1),
        )
        db_session.add(snap)
        db_session.flush()
        assert snap.spread_home is None

    def test_relationship_to_game(self, db_session, sample_odds):
        snap = sample_odds[0]
        assert snap.game is not None
        assert snap.game.season == 2025

    def test_default_is_opening_false(self, db_session, sample_games):
        snap = OddsSnapshot(
            game_id=sample_games[0].id, source="test",
            captured_at=datetime(2025, 9, 2),
        )
        db_session.add(snap)
        db_session.flush()
        assert snap.is_opening is False


# ---------------------------------------------------------------------------
# Pick model
# ---------------------------------------------------------------------------

class TestPickModel:
    def test_create_pick(self, db_session, user_alice, sample_games, teams):
        game = sample_games[0]
        pick = Pick(
            user_id=user_alice.id, game_id=game.id,
            season=2025, week=1, contest_type="millions",
            picked_team_id=teams["KC"].id,
        )
        db_session.add(pick)
        db_session.flush()
        assert pick.id is not None
        assert pick.created_at is not None

    def test_pick_relationships(self, db_session, user_alice, sample_games, teams):
        game = sample_games[0]
        pick = Pick(
            user_id=user_alice.id, game_id=game.id,
            season=2025, week=1, contest_type="survivor",
            picked_team_id=teams["BUF"].id,
        )
        db_session.add(pick)
        db_session.flush()
        db_session.refresh(pick)
        assert pick.user.username == "alice"
        assert pick.picked_team.abbreviation == "BUF"

    def test_pick_with_comment(self, db_session, user_alice, sample_games, teams):
        game = sample_games[0]
        pick = Pick(
            user_id=user_alice.id, game_id=game.id,
            season=2025, week=1, contest_type="millions",
            picked_team_id=teams["KC"].id,
            comment="KC looks strong at home",
        )
        db_session.add(pick)
        db_session.flush()
        assert pick.comment == "KC looks strong at home"


# ---------------------------------------------------------------------------
# ConsensusPick model
# ---------------------------------------------------------------------------

class TestConsensusPickModel:
    def test_create_consensus_pick(self, db_session, sample_games, teams):
        cp = ConsensusPick(
            season=2025, week=1, contest_type="millions",
            game_id=sample_games[0].id, picked_team_id=teams["KC"].id,
        )
        db_session.add(cp)
        db_session.flush()
        assert cp.id is not None
        assert cp.decided_at is not None

    def test_consensus_pick_nullable_game_id(self, db_session, teams):
        cp = ConsensusPick(
            season=2025, week=1, contest_type="survivor",
            game_id=None, picked_team_id=teams["KC"].id,
        )
        db_session.add(cp)
        db_session.flush()
        assert cp.game_id is None

    def test_consensus_pick_relationships(self, db_session, sample_games, teams):
        cp = ConsensusPick(
            season=2025, week=1, contest_type="millions",
            game_id=sample_games[0].id, picked_team_id=teams["BUF"].id,
        )
        db_session.add(cp)
        db_session.flush()
        db_session.refresh(cp)
        assert cp.picked_team.abbreviation == "BUF"
