# Architecture Decisions

This document explains *why* the system is built the way it is. Not what the code does — that's in `CONTRIBUTING.md` and the code itself — but the reasoning behind the structural choices.

## The problem being solved

Three people share one entry in two NFL contests (Circa Millions and Circa Survivor). Every week they need to:

1. Research games using odds data, line movement, and team stats
2. Each submit their individual picks
3. Arrive at consensus on which picks to lock in
4. Track constraints (survivor team reuse, special slate pools)

The core challenge isn't building a sportsbook — it's building a **collaborative decision tool** backed by data that's good enough to be an edge.

## Why this tech stack

**FastAPI + SQLAlchemy + SQLite** — The audience is 3 people on a homelab. SQLite eliminates ops overhead (no database server, backups are `cp circa.db circa.db.bak`) while SQLAlchemy's ORM means swapping to Postgres later is a migration away, not a rewrite. FastAPI was chosen for its automatic OpenAPI docs (useful for debugging), Pydantic validation (catches bad data at the boundary), and the `Depends()` system which keeps route handlers clean.

**React + Vite + Tailwind** — Standard choices for a small SPA. No state management library because the app doesn't need one — auth state lives in context, everything else is local component state fetched on mount. Adding Redux or Zustand for 5 pages would be premature.

**No Docker (yet)** — For a 3-user homelab app, `uvicorn` behind Tailscale is sufficient. Containerization adds value when there's a deployment pipeline or multiple environments. It's a future step, not a prerequisite.

## Data model decisions

### Why OddsSnapshot is append-only

The most important feature of this app is line movement tracking. Odds aren't a "current state" — they're a time series. A spread that opened at -3 and closed at -7 tells a completely different story than one that was -7 all week. That story is the edge.

So `OddsSnapshot` is designed as an append-only log: one row per game per source per point in time. No updates, no "latest" column on the game itself. The latest odds are derived at query time (`ORDER BY captured_at DESC LIMIT 1`). This is slightly more expensive to query but means we never lose historical data and the write path is trivially simple.

The `is_opening` flag on each snapshot marks the first captured line for that game/source pair. Opening lines are the market's initial assessment before public money moves them — they're a baseline for measuring sharp action.

### Why source is a column, not a table

Every odds snapshot and stat snapshot carries a `source` string (`pinnacle`, `espn`, `market_consensus`, etc.). An alternative would be a normalized `Sources` table with foreign keys. We chose the string approach because:

- Sources are a classification tag, not an entity with behavior or relationships
- New sources can be added by ingestion scripts without touching the schema
- Queries like "show me pinnacle's line for this game" read naturally as `WHERE source = 'pinnacle'`
- There are ~5 sources total and no risk of the string diverging since ingestion scripts own the values

### Why Pick and ConsensusPick are separate tables

A `Pick` is one person's opinion. A `ConsensusPick` is the group's commitment. They have different lifecycles:

- Picks are created, changed, and deleted freely by individual users throughout the week
- Consensus picks are locked once (after discussion) and represent the final submission
- Survivor reuse rules check against `ConsensusPick`, not `Pick` — you can *suggest* the Chiefs every week, but once they're *locked*, they're burned

Merging these into one table with a `status` column was considered, but it would mean survivor constraint checks need to filter by status, picks listings need to exclude locked rows, and the conceptual distinction ("my pick" vs "our pick") gets muddied. Two small tables with clear semantics beats one table with conditional logic.

### Why ConsensusPick.game_id is nullable

A consensus pick records "we're taking the Chiefs this week in survivor." The game itself is implicit (there's only one Chiefs game per week). Making `game_id` nullable allows locking a team pick even when the game context doesn't matter — particularly useful for survivor where the pick is about the team, not the game.

For millions picks, `game_id` is always populated because the pick is against a specific spread in a specific game.

### Why stats are stored as weekly snapshots, not season totals

`TeamStatSnapshot` stores cumulative stats *as of* a given week. Week 8's row contains the team's numbers through 8 games. This seems redundant (week 8 contains week 7's data plus one game), but it enables:

- **Trend analysis** — plot how a defense improved or collapsed over time
- **Week-specific matchup context** — when reviewing a Week 10 pick, show stats through Week 9, not end-of-season stats
- **No recomputation** — displaying "Chiefs PPG through Week 12" is a single row lookup, not an aggregation

The cost is storage (32 teams × 18 weeks = 576 rows per season), which is negligible.

### Why scores live on the Game model

`score_home` and `score_away` are columns on `Game` rather than a separate `GameResult` table. A game has exactly one final score — there's no cardinality mismatch or lifecycle difference that would justify a separate entity. Nullable columns handle the "game hasn't happened yet" state cleanly.

## Authentication design

### Why JWT, not sessions

The app is designed for homelab deployment behind Tailscale. JWT means stateless auth — no session store, no Redis, no cookie configuration across domains. The backend is a pure API server; the frontend stores the token in `localStorage` and attaches it via axios interceptor.

The tradeoff is that tokens can't be revoked before expiry (24 hours). For a 3-user trusted team app, this is acceptable. If the user base grew or security requirements tightened, switching to short-lived tokens + refresh tokens would be the next step.

### Why passwords and not just Tailscale identity

Tailscale provides network-level access control, but the app still needs to know *which* of the three users is making picks. User accounts with passwords are the simplest way to establish identity and associate picks with people. SSO via Tailscale's OIDC would be cleaner but adds integration complexity that doesn't pay off at this scale.

## Ingestion architecture

### Why disk caching

External APIs are the app's biggest operational risk:

- **the-odds-api.com** has monthly request limits (paid tier)
- **ESPN** is free but undocumented — aggressive scraping could get blocked
- **covers.com** is scraped HTML that could change format at any time

Disk caching (JSON files in `ingestion/cache/`) means a failed or rate-limited request doesn't break the app. It also means development and testing don't burn API quota. Cache freshness is controlled by TTL (24 hours for stats, configurable for odds).

The cache is intentionally simple — flat files, not Redis or memcached. For a system that fetches data a few times a day, filesystem I/O is more than adequate and introduces zero dependencies.

### Why the normalizer is separate from the fetcher

`team_stats_fetcher.py` handles network + caching. `team_stats_normalizer.py` handles field mapping. This split exists because:

- ESPN's API response structure has changed over time (we already handle two different layouts). The normalizer isolates this instability.
- Normalization logic is independently testable — `test_team_stats_normalizer.py` tests field mapping without network calls
- Adding a new source (say, Pro Football Reference) means writing a new fetcher and a new normalizer function, plugging into the same `TeamStatSnapshot` model

### Why synthetic line movement

Real line movement data for completed games is effectively lost — live odds APIs don't retain historical snapshots, and scraping sites only preserve opening/closing lines. Rather than leave the line movement charts empty for backfilled seasons, we synthesize intermediate points:

- Opening line (from existing data or derived from closing line + offset)
- 4 intermediate points interpolated with random jitter
- Closing line (real data from covers.com)

The synthesis is seeded with `random.seed(season)` so it's deterministic — running the backfill twice produces the same data. The jitter uses half-point increments and per-book offsets to simulate real market behavior where books shade lines differently.

This is explicitly not real data. It's realistic enough to exercise the UI and provide visual context, but no analysis should treat synthetic movement as market signal.

## Frontend architecture

### Why no state management library

The app has 5 pages. Auth state is in a context provider. Everything else is fetched on mount and held in local `useState`. There's no cross-page state that would benefit from a store — navigating to a new page fetches fresh data.

If the app grew to need real-time updates (WebSocket odds feeds) or complex cross-page state (draft boards, multi-step workflows), a store would make sense. Until then, `useState` + `useEffect` + context is the right level of complexity.

### Why Vite proxy instead of CORS-only

The frontend calls `api.get('/schedule/games')` — no `http://localhost:8000` prefix. Vite's dev server proxies `/api` to the backend. This mirrors production (where both would be served from the same origin behind a reverse proxy) and avoids CORS configuration headaches. The backend still has CORS enabled for `localhost:5173` as a fallback, but the proxy is the primary mechanism.

### Why lazy="joined" on relationships

Most ORM relationships use `lazy="joined"` (eager loading via SQL JOIN). This means fetching a `Game` automatically loads its `home_team` and `away_team` in one query. The alternative — `lazy="select"` (default) — would issue separate queries for each relationship access, leading to N+1 problems when listing games.

The exception is `Game.odds_snapshots` which uses `lazy="dynamic"` because a game can have hundreds of snapshots and we usually want to filter or paginate them rather than load all at once.

## What I'd change with hindsight

### Denormalized season/week on Pick

`Pick` stores `season` and `week` even though they're derivable from the associated `Game`. This was done to simplify query filters (`WHERE season = 2025 AND week = 3`) without joining to games. It works but creates a potential inconsistency if a game's week ever changed. At this scale it's fine; in a larger system I'd enforce it via a database trigger or remove the duplication.

### datetime.utcnow() deprecation

The codebase uses `datetime.utcnow()` in several places, which is deprecated in Python 3.12+. Should be `datetime.now(timezone.utc)`. The tests surface this as warnings. It's a mechanical fix but worth noting as tech debt.

### SQLAlchemy legacy .get() calls

Some routers use `db.query(Model).get(id)` which SQLAlchemy 2.0 considers legacy. The modern equivalent is `db.get(Model, id)`. Another mechanical fix.
