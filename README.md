# Circa Contest Planner

A collaborative NFL contest planning app for [Circa Millions](https://www.circasports.com/) and [Circa Survivor](https://www.circasports.com/). Built for a 3-person team to research, discuss, and lock in weekly picks using real-time odds data, team stats, and line movement analysis.

## Architecture

```
circa/
├── backend/                  # Python FastAPI API + data ingestion
│   ├── app/
│   │   ├── main.py           # App init, router registration, CORS, scheduler
│   │   ├── config.py         # Settings (env vars, defaults)
│   │   ├── database.py       # SQLAlchemy engine + session
│   │   ├── seed.py           # Seeds 32 NFL teams
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── routers/          # FastAPI endpoint groups
│   │   ├── schemas/          # Pydantic request/response validation
│   │   └── services/         # Auth (JWT, bcrypt)
│   ├── ingestion/            # Data pipelines (ESPN, the-odds-api)
│   │   ├── schedule_fetcher.py
│   │   ├── odds_fetcher.py
│   │   ├── team_stats_fetcher.py
│   │   └── team_stats_normalizer.py
│   ├── alembic/              # Database migrations
│   └── tests/                # pytest suite
├── frontend/                 # React + Vite SPA
│   └── src/
│       ├── pages/            # Schedule, GameDetail, Picks, Consensus, Login
│       ├── components/       # GameCard, OddsChart, SurvivorTracker, Navbar
│       ├── context/          # AuthContext (JWT state management)
│       └── api.js            # Axios instance w/ auth interceptor
└── spec.md                   # Original requirements
```

## Tech Stack

| Layer       | Technology                                      |
|-------------|------------------------------------------------ |
| Backend     | Python, FastAPI, SQLAlchemy, Pydantic            |
| Database    | SQLite (Alembic migrations, swappable to Postgres) |
| Auth        | JWT (python-jose) + bcrypt password hashing      |
| Frontend    | React 19, Vite, Tailwind CSS, Recharts           |
| Ingestion   | httpx, BeautifulSoup4, APScheduler               |
| Testing     | pytest with FastAPI TestClient                   |

## Data Models

### Core

- **Team** - 32 NFL teams (abbreviation, name, conference, division)
- **Game** - Season schedule (week, home/away teams, game time, slate type)
- **User** - App users (username, email, password hash)

### Odds Tracking

- **OddsSnapshot** - Point-in-time odds capture per game/source
  - Spread (home perspective), total, moneyline (both sides)
  - `is_opening` flag marks the opening line for each game/source
  - Multiple snapshots over time enable line movement charts

### Picks & Consensus

- **Pick** - Individual user pick (team, game, contest type, optional comment)
- **ConsensusPick** - Locked group pick representing the team's final decision

### Team Statistics

- **TeamStatSnapshot** - Per-team cumulative stats as of a given week
  - Offense: PPG, yards/game (total, passing, rushing), turnovers, red zone TD%, 3rd down %
  - Defense: points allowed, yards allowed, sacks, takeaways
  - Situational: point differential
- **TeamStanding** - Season record, division/conference rank, playoff seed, SOS

## API Endpoints

### Auth (`/api/auth`)
| Method | Path        | Description              |
|--------|-------------|--------------------------|
| POST   | `/register` | Create account           |
| POST   | `/login`    | Get JWT token            |
| GET    | `/me`       | Current user (protected) |

### Schedule (`/api/schedule`)
| Method | Path            | Description                              |
|--------|-----------------|------------------------------------------|
| GET    | `/teams`        | All NFL teams                            |
| GET    | `/games`        | Games (filter: season, week, team)       |
| GET    | `/games/{id}`   | Single game with team details            |

### Odds (`/api/odds`)
| Method | Path                  | Description                        |
|--------|-----------------------|------------------------------------|
| GET    | `/game/{id}`          | Full odds history for a game       |
| GET    | `/game/{id}/latest`   | Most recent odds per source        |

### Picks (`/api/picks`)
| Method | Path                  | Description                              |
|--------|-----------------------|------------------------------------------|
| GET    | `/`                   | User's picks (filter: season, week, type)|
| POST   | `/`                   | Submit a pick                            |
| DELETE | `/{id}`               | Remove a pick                            |
| GET    | `/survivor/used`      | Teams already used in survivor           |
| GET    | `/survivor/slate-warning` | Warns if pick reduces special slate pool |

### Consensus (`/api/consensus`)
| Method | Path          | Description                           |
|--------|---------------|---------------------------------------|
| GET    | `/picks`      | All users' picks for a week (voting)  |
| GET    | `/locked`     | Locked consensus picks                |
| POST   | `/lock`       | Lock a consensus pick                 |
| DELETE | `/lock/{id}`  | Unlock a consensus pick               |

### Team Stats (`/api/team-stats`)
| Method | Path                        | Description                           |
|--------|-----------------------------|---------------------------------------|
| GET    | `/stats`                    | Team stat snapshots (filter by week)  |
| GET    | `/stats/{abbr}/history`     | Week-by-week stat progression         |
| GET    | `/rankings`                 | Rank teams by any stat column         |
| GET    | `/standings`                | Season standings (filter by conf)     |
| GET    | `/matchup`                  | Side-by-side comparison of two teams  |

## Data Ingestion

Three pipelines fetch and normalize external data:

**Schedule** (`schedule_fetcher.py`) - ESPN public API. Fetches all 18 weeks, detects special slates (Thanksgiving, Christmas) by date.

**Odds** (`odds_fetcher.py`) - [the-odds-api.com](https://the-odds-api.com/). Captures spreads, totals, and moneylines from sharp and bettor-friendly books (Pinnacle, Bookmaker, DraftKings, FanDuel, BetMGM). Disk-cached to respect rate limits. Configurable fetch interval.

**Team Stats** (`team_stats_fetcher.py` + `team_stats_normalizer.py`) - ESPN team stats and standings endpoints. Normalizes raw data into per-game rates, derived stats (red zone TD%, takeaways), and standings. 24-hour cache TTL per team/week.

All pipelines tag data with source, enabling multi-provider support and future scraping additions.

## Contests

### Circa Millions
- Pick 5 NFL games per week against the spread
- Team consensus locks exactly 5 picks per week
- Teams can be reused across weeks

### Circa Survivor
- Pick 1 team per week to win outright
- Once a team is locked in consensus, it cannot be reused for the season
- Special slate awareness: the app warns when a pick would reduce the available team pool for Thanksgiving/Christmas weeks

## Frontend Pages

- **Schedule** - Browse games by week, filter by team, view latest spreads
- **Game Detail** - Line movement chart (Recharts) showing spread progression across sources over time
- **Picks** - Toggle between Millions/Survivor modes, select picks with comments, see slate warnings
- **Consensus** - View all teammates' picks grouped by game, vote counts, lock/unlock final picks
- **Login** - Register and authenticate

## Getting Started

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Set SECRET_KEY, ODDS_API_KEY, CURRENT_SEASON

# Run migrations and seed
alembic upgrade head
python -c "from app.seed import seed_teams; from app.database import SessionLocal; seed_teams(SessionLocal())"

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev  # Starts on http://localhost:5173
```

### Ingestion

```bash
cd backend

# Fetch schedule
python -m ingestion.schedule_fetcher

# Fetch odds (requires ODDS_API_KEY)
python -m ingestion.odds_fetcher

# Fetch team stats
python -m ingestion.team_stats_fetcher
```

### Tests

```bash
cd backend
pytest
```

## Configuration

| Variable                      | Description                        | Default          |
|-------------------------------|------------------------------------|------------------|
| `SECRET_KEY`                  | JWT signing key                    | (change in prod) |
| `ODDS_API_KEY`                | the-odds-api.com key               | -                |
| `CURRENT_SEASON`              | Active NFL season                  | `2025`           |
| `DATABASE_URL`                | SQLAlchemy connection string       | `sqlite:///circa.db` |
| `ODDS_FETCH_INTERVAL_MINUTES` | Odds cache freshness               | `60`             |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token lifetime                 | `1440` (24hr)    |

## Deployment

Designed for homelab hosting behind a [Tailscale](https://tailscale.com/) tunnel, giving teammates secure remote access without exposing the home network. SQLite works well for the 3-user team; Alembic migrations make switching to PostgreSQL straightforward if needed.
