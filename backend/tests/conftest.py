"""
Shared fixtures for the Circa test suite.

Uses an in-memory SQLite database so every test module gets a fresh,
isolated schema with no I/O side-effects.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Team, Game, OddsSnapshot, User, Pick, ConsensusPick
from app.services.auth import hash_password, create_access_token

# ---------------------------------------------------------------------------
# Engine / session setup
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    """One in-memory SQLite engine shared across the entire test session."""
    _engine = create_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()


@pytest.fixture()
def db_session(engine):
    """
    Function-scoped database session.
    Wraps each test in a transaction that is rolled back at the end,
    keeping tests fully isolated without re-creating the schema.
    """
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(bind=connection)
    session = TestingSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    """TestClient wired to the in-memory session via dependency override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def teams(db_session):
    """Seed a minimal set of NFL teams sufficient for all test scenarios."""
    team_data = [
        ("KC",  "Kansas City Chiefs",       "AFC", "West"),
        ("BUF", "Buffalo Bills",             "AFC", "East"),
        ("SF",  "San Francisco 49ers",       "NFC", "West"),
        ("DAL", "Dallas Cowboys",            "NFC", "East"),
        ("DET", "Detroit Lions",             "NFC", "North"),
        ("GB",  "Green Bay Packers",         "NFC", "North"),
        ("PHI", "Philadelphia Eagles",       "NFC", "East"),
        ("BAL", "Baltimore Ravens",          "AFC", "North"),
        ("MIA", "Miami Dolphins",            "AFC", "East"),
        ("NE",  "New England Patriots",      "AFC", "East"),
        ("CHI", "Chicago Bears",             "NFC", "North"),
        ("MIN", "Minnesota Vikings",         "NFC", "North"),
    ]
    rows = [
        Team(abbreviation=a, name=n, conference=c, division=d)
        for a, n, c, d in team_data
    ]
    db_session.add_all(rows)
    db_session.flush()
    return {t.abbreviation: t for t in rows}


@pytest.fixture()
def sample_games(db_session, teams):
    """Create a few games across weeks and slates."""
    kc  = teams["KC"]
    buf = teams["BUF"]
    sf  = teams["SF"]
    dal = teams["DAL"]
    det = teams["DET"]
    chi = teams["CHI"]
    phi = teams["PHI"]
    min_ = teams["MIN"]

    base = datetime(2025, 9, 7, 13, 0, 0)

    games = [
        # week 1 – regular
        Game(season=2025, week=1, home_team_id=kc.id,  away_team_id=buf.id, game_time=base,                  slate="regular"),
        Game(season=2025, week=1, home_team_id=sf.id,  away_team_id=dal.id, game_time=base + timedelta(hours=3), slate="regular"),
        # week 2 – regular
        Game(season=2025, week=2, home_team_id=buf.id, away_team_id=sf.id,  game_time=base + timedelta(weeks=1), slate="regular"),
        # Thanksgiving games (special slate)
        Game(season=2025, week=12, home_team_id=det.id, away_team_id=chi.id, game_time=datetime(2025, 11, 27, 12, 30), slate="thanksgiving"),
        Game(season=2025, week=12, home_team_id=dal.id, away_team_id=phi.id, game_time=datetime(2025, 11, 27, 16, 30), slate="thanksgiving"),
        Game(season=2025, week=12, home_team_id=min_.id, away_team_id=buf.id, game_time=datetime(2025, 11, 27, 20, 30), slate="thanksgiving"),
    ]
    db_session.add_all(games)
    db_session.flush()
    return games


@pytest.fixture()
def sample_odds(db_session, sample_games):
    """Attach opening + closing odds snapshots to the first game."""
    game = sample_games[0]
    base_time = datetime(2025, 9, 1, 12, 0, 0)
    snapshots = [
        OddsSnapshot(
            game_id=game.id, source="pinnacle",
            spread_home=-3.0, total=52.5, moneyline_home=-165, moneyline_away=140,
            is_opening=True, captured_at=base_time,
        ),
        OddsSnapshot(
            game_id=game.id, source="pinnacle",
            spread_home=-3.5, total=53.0, moneyline_home=-170, moneyline_away=145,
            is_opening=False, captured_at=base_time + timedelta(hours=12),
        ),
        OddsSnapshot(
            game_id=game.id, source="draftkings",
            spread_home=-3.0, total=52.0, moneyline_home=-160, moneyline_away=135,
            is_opening=False, captured_at=base_time + timedelta(hours=6),
        ),
        # second game – one snapshot
        OddsSnapshot(
            game_id=sample_games[1].id, source="pinnacle",
            spread_home=-6.5, total=48.0, moneyline_home=-240, moneyline_away=195,
            is_opening=True, captured_at=base_time,
        ),
    ]
    db_session.add_all(snapshots)
    db_session.flush()
    return snapshots


@pytest.fixture()
def user_alice(db_session):
    """A registered user: alice."""
    u = User(
        username="alice",
        email="alice@example.com",
        password_hash=hash_password("secret123"),
    )
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture()
def user_bob(db_session):
    """A second registered user: bob."""
    u = User(
        username="bob",
        email="bob@example.com",
        password_hash=hash_password("pass456"),
    )
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture()
def alice_token(user_alice):
    """Valid JWT for alice."""
    return create_access_token(user_alice.id)


@pytest.fixture()
def bob_token(user_bob):
    """Valid JWT for bob."""
    return create_access_token(user_bob.id)


@pytest.fixture()
def auth_headers_alice(alice_token):
    return {"Authorization": f"Bearer {alice_token}"}


@pytest.fixture()
def auth_headers_bob(bob_token):
    return {"Authorization": f"Bearer {bob_token}"}
