# Contributing to Circa

Technical guide for developers joining the project. Covers the architecture, patterns, data flow, and conventions you need to understand before making changes.

## Setup

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set SECRET_KEY, ODDS_API_KEY, CURRENT_SEASON
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                  # http://localhost:5173, proxied to :8000
```

Vite proxies `/api` requests to the backend — see `frontend/vite.config.js`. This means the frontend makes calls like `api.get('/schedule/games')` and Vite rewrites them to `http://localhost:8000/api/schedule/games`.

## How the backend is organized

```
backend/app/
├── main.py          # FastAPI app, CORS, router registration
├── config.py        # Settings loaded from env / .env
├── database.py      # SQLAlchemy engine, session factory, get_db dependency
├── seed.py          # Seeds 32 NFL teams on first run
├── models/          # SQLAlchemy ORM models (one file per domain entity)
├── schemas/         # Pydantic request/response validation (mirrors models/)
├── routers/         # FastAPI endpoint groups (one file per domain)
└── services/        # Shared business logic (currently just auth)
```

### Request lifecycle

Every request follows the same pattern:

1. Router function declares dependencies via `Depends()`
2. `get_db` yields a SQLAlchemy session (auto-closed after request)
3. `get_current_user` decodes the JWT and returns the `User` row (for protected routes)
4. Router queries/mutates via the session, returns a Pydantic response model

Example from `routers/auth.py`:
```python
@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
```

FastAPI + Pydantic's `from_attributes=True` handles the ORM → JSON serialization automatically.

### Adding a new endpoint

1. **Model** — if you need a new table, add it in `models/`, register it in `models/__init__.py`
2. **Schema** — add request/response classes in `schemas/`. Use `model_config = ConfigDict(from_attributes=True)` for ORM response models
3. **Router** — add the endpoint in the relevant `routers/` file. Use `Depends(get_db)` for DB access, `Depends(get_current_user)` for auth
4. **Register** — if it's a new router file, add `app.include_router(your_router.router)` in `main.py`
5. **Migration** — run `alembic revision --autogenerate -m "description"` then `alembic upgrade head`
6. **Test** — add tests in `tests/`

### Adding a new model

Models use SQLAlchemy 2.0 `Mapped` style:

```python
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Example(Base):
    __tablename__ = "examples"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))

    team = relationship("Team", lazy="joined")
```

After creating the model, import it in `models/__init__.py` so Alembic picks it up during autogeneration.

## Data model

The core relationships:

```
Team (32 NFL teams)
  ├── Game (home_team_id, away_team_id) — 272 per regular season
  │     ├── OddsSnapshot (many per game — tracks line movement over time)
  │     ├── Pick (user pick for a specific game)
  │     └── score_home, score_away (final scores)
  ├── TeamStatSnapshot (per-team stats as of a given week)
  ├── TeamStanding (season-level record, one per team per season)
  ├── Pick (picked_team_id — which team the user chose)
  └── ConsensusPick (picked_team_id — the group's locked final pick)
```

**Key design decisions:**

- **OddsSnapshot** stores many rows per game to track line movement. Each snapshot is tagged with `source` (pinnacle, draftkings, etc.) and `captured_at`. The `is_opening` flag marks the first snapshot per game/source.
- **Pick vs ConsensusPick** — `Pick` is an individual user's preference. `ConsensusPick` is the locked group decision. Survivor reuse checks run against `ConsensusPick`, not `Pick`.
- **TeamStatSnapshot** stores cumulative stats as-of a week. Week 8 has the team's stats through 8 games. This allows trend analysis across the season.
- All stats and odds are tagged with `source` to support multiple data providers.

## Contests

Understanding the two contests is essential for working on picks/consensus logic.

### Circa Millions
- 5 picks per week against the spread
- Teams can be reused across weeks
- Enforced in `routers/consensus.py` — `lock_consensus_pick` checks count < 5

### Circa Survivor
- 1 pick per week, team must win outright
- Once a team is locked via consensus, it **cannot be reused** for the rest of the season
- Enforced in both `routers/picks.py` (warns users) and `routers/consensus.py` (blocks locking)
- Special slates (Thanksgiving, Christmas) have limited team pools — `picks.py:check_slate_warning` alerts users when a pick reduces options

## Data ingestion

```
backend/ingestion/
├── schedule_fetcher.py          # ESPN scoreboard → Game rows
├── odds_fetcher.py              # the-odds-api.com → OddsSnapshot (live/current)
├── historical_odds_scraper.py   # covers.com → OddsSnapshot (closing lines)
├── team_stats_fetcher.py        # ESPN team stats + standings → snapshots
├── team_stats_normalizer.py     # Maps ESPN field names to our schema
├── backfill_season.py           # Orchestrates full-season backfill
└── cache/                       # Disk cache for API responses
```

### How ingestion works

Each fetcher follows the same pattern:
1. Check disk cache (avoid redundant API calls)
2. Fetch from external API
3. Normalize the response into our schema
4. Upsert into the database

**ESPN API** — free, no key required. Used for schedule, team stats, standings, and scores. The response structure has changed over time, so `team_stats_fetcher.py` checks both `results.stats.categories` (current) and `splits.categories` (legacy).

**the-odds-api.com** — requires API key, rate limited. Used for live odds during the season. Captures spreads, totals, and moneylines from preferred books.

**covers.com** — scraped for historical closing lines. Provides spread and total for completed games.

### Adding a new data source

1. Create a fetcher in `ingestion/`
2. Add normalization logic (either inline or in `team_stats_normalizer.py`)
3. Tag all records with a unique `source` string so data from different providers doesn't collide
4. Use the disk cache pattern — store raw responses in `ingestion/cache/`

### Backfilling a season

```bash
python -m ingestion.backfill_season --season 2025
```

This runs: scores (ESPN) → closing lines (covers.com) → synthesized line movement → team stats (18 weeks) → standings. Uses `random.seed(season)` for deterministic synthetic data.

## How the frontend is organized

```
frontend/src/
├── App.jsx                # Router setup, ProtectedRoute wrapper
├── api.js                 # Axios instance with JWT interceptor
├── context/
│   └── AuthContext.jsx    # Auth state: user, login, register, logout
├── pages/
│   ├── Login.jsx          # Register + login forms
│   ├── Schedule.jsx       # Week-by-week game list with filters
│   ├── GameDetail.jsx     # Line movement chart + matchup stats
│   ├── Picks.jsx          # User pick selection (millions/survivor)
│   └── Consensus.jsx      # Group voting + lock/unlock
└── components/
    ├── Navbar.jsx          # Nav links + user menu
    ├── GameCard.jsx        # Reusable game display with odds
    ├── OddsChart.jsx       # Recharts line chart for spread movement
    ├── MatchupStats.jsx    # Side-by-side team stat comparison
    └── SurvivorTracker.jsx # Shows used survivor teams
```

### State management

There is no global state library. State is managed through:

- **AuthContext** — user session, JWT token in localStorage
- **Local component state** — `useState` for filters, selections, form data
- **API calls** — `useEffect` fetches data on mount or when dependencies change

### Auth flow

1. User registers or logs in → backend returns JWT
2. Token stored in `localStorage`
3. `api.js` interceptor attaches `Authorization: Bearer {token}` to every request
4. On 401 response, interceptor clears token and redirects to `/login`
5. `AuthContext` checks token on mount by calling `GET /api/auth/me`

### Adding a new page

1. Create the component in `pages/`
2. Add a `<Route>` in `App.jsx`, wrapped in `<ProtectedRoute>` if auth is required
3. Add a nav link in `components/Navbar.jsx`
4. Use `api.get()`/`api.post()` to call backend endpoints — the proxy handles routing

## Database migrations

We use Alembic for schema versioning. The migration environment is configured in `backend/alembic/env.py` to import all models from `app.models`.

```bash
# Generate a migration after changing a model
alembic revision --autogenerate -m "add foo column to bar"

# Apply migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

SQLite is used for development. The schema is designed to be portable to PostgreSQL — avoid SQLite-specific syntax in migrations.

## Testing

```bash
cd backend
pytest           # run all 202 tests
pytest -v        # verbose output
pytest -k "auth" # run only tests matching "auth"
```

### How tests work

Tests use an **in-memory SQLite database** — no disk I/O, no state leaking between tests. The setup is in `tests/conftest.py`:

- `engine` fixture (session-scoped) — creates tables once
- `db_session` fixture (function-scoped) — wraps each test in a transaction that rolls back
- `client` fixture — FastAPI `TestClient` wired to the in-memory session via `dependency_overrides`

### Writing a test

```python
def test_my_feature(client, auth_headers_alice, teams, sample_games):
    """Use fixtures to set up state, then hit the API."""
    resp = client.get("/api/schedule/games?week=1", headers=auth_headers_alice)
    assert resp.status_code == 200
    assert len(resp.json()) == 2  # sample_games creates 2 week-1 games
```

Available fixtures: `teams`, `sample_games`, `sample_odds`, `user_alice`, `user_bob`, `alice_token`, `bob_token`, `auth_headers_alice`, `auth_headers_bob`.

For protected endpoints, pass `headers=auth_headers_alice`. For unprotected endpoints (health, register, login), no headers needed.

### Test conventions

- Group related tests in classes: `class TestCreatePick`, `class TestSurvivorReuse`
- Test the happy path, edge cases, and auth guards
- Each test is independent — don't rely on test execution order

## Environment variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `SECRET_KEY` | JWT signing | Yes (change from default) |
| `ODDS_API_KEY` | the-odds-api.com | For live odds only |
| `CURRENT_SEASON` | Active NFL season (e.g. 2025) | Has default |
| `DATABASE_URL` | SQLAlchemy connection string | Has default (SQLite) |
| `ODDS_FETCH_INTERVAL_MINUTES` | Cache freshness for odds | Has default (60) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime | Has default (1440) |

## Git workflow

- Branch from `master`
- Branch naming: `feature/`, `fix/`, `refactor/`, `test/`, `docs/`
- Tests must pass before merging
- Merge PRs via GitHub
