# Circa Contest Planner

Collaborative NFL contest-picking app for a 3-person team splitting one entry each in
Circa Millions (5 picks/week against the spread) and Circa Survivor (1 pick/week, team
burned once locked). FastAPI + SQLAlchemy/SQLite backend with data-ingestion pipelines
(schedule, odds, team stats) feeding a React + Vite frontend. Built for homelab
deployment behind Tailscale, not public hosting.

## Reference docs — read before building

- `spec.md` — original product requirements and the Millions/Survivor contest rules;
  read before touching picks, consensus, or survivor-reuse logic
- `ARCHITECTURE.md` — *why*, not *what*: append-only odds, JWT-not-sessions, no Docker,
  synthetic line movement; read before changing the data model or auth
- `CONTRIBUTING.md` — day-to-day dev guide: request lifecycle, how to add an
  endpoint/model/page, ingestion pattern, test fixtures; read before adding a router,
  model, or ingestion source
- `README.md` — project overview, full API endpoint table, ingestion pipeline summary

## Commands

Backend (from `backend/`):
```bash
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
alembic upgrade head
python -c "from app.seed import seed_teams; from app.database import SessionLocal; seed_teams(SessionLocal())"
uvicorn app.main:app --reload --port 8000
pytest                                            # pytest.ini: testpaths=tests, -v --tb=short
pytest -k "auth"                                  # filter by name/keyword
alembic revision --autogenerate -m "description"  # after changing a model, then `alembic upgrade head`
```

Frontend (from `frontend/`):
```bash
npm install
npm run dev     # :5173, proxies /api/* to :8000 — see vite.config.js
npm run build   # production build; this is the frontend's CI gate (no separate typecheck)
npm run lint    # eslint; NOT run in CI — run it yourself before a JS/JSX PR
```

There is no backend lint/type-check step (no ruff or mypy in `requirements.txt` or CI),
despite a stray `.ruff_cache/` at the repo root — don't assume one runs.

## CI

`.github/workflows/ci.yml` runs two independent required jobs: `pytest` in `backend/`
and `npm run build` in `frontend/`. No Docker, no deploy step.

## Conventions / gotchas

- `Pick` (individual, freely mutable) vs `ConsensusPick` (locked, group decision) are
  separate tables. Survivor reuse checks and the Millions 5-pick cap are enforced
  against `ConsensusPick` only, never `Pick`.
- `OddsSnapshot` is append-only — never update or delete a row. "Latest odds" is a query
  (`ORDER BY captured_at DESC LIMIT 1`); `is_opening` marks each game/source's first row.
- `bcrypt` is pinned to `4.0.1` in `backend/requirements.txt` because newer bcrypt breaks
  `passlib==1.7.4`'s version probe — don't bump one without the other.
- Ingestion sources (`backend/ingestion/`) always split fetch+cache from normalize, e.g.
  `team_stats_fetcher.py` / `team_stats_normalizer.py` — copy that split for a new source,
  and tag every row with a `source` string.
- Backfilled/historical line movement is synthetic (`random.seed(season)`-derived jitter
  around real opening/closing lines) — never treat it as real market signal.
- Tests run against an in-memory SQLite DB with per-test transaction rollback
  (`tests/conftest.py`) — use the existing fixtures (`teams`, `sample_games`,
  `auth_headers_alice`, etc.) rather than touching the real `circa.db`.
- Frontend has no state library: auth lives in `AuthContext`, everything else is
  `useState`/`useEffect` fetched on mount — don't add Redux/Zustand for a new page.

## Environment variables (`backend/.env`)

`SECRET_KEY`, `ODDS_API_KEY` (the-odds-api.com, live odds only), `CURRENT_SEASON`,
`DATABASE_URL`, `ODDS_FETCH_INTERVAL_MINUTES`, `ACCESS_TOKEN_EXPIRE_MINUTES` — see
`CONTRIBUTING.md` for defaults. No `.env.example` currently exists in the repo despite
docs saying `cp .env.example .env`.

## Git workflow

Branch from `master`; prefixes `feature/`, `fix/`, `refactor/`, `test/`, `docs/`; tests
must pass before merge; merge via GitHub PR.
