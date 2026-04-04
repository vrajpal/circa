"""Fetch odds from the-odds-api.com.

Caches raw API responses to disk to avoid burning rate-limited requests.
Only makes a new API call if the cache is older than the configured interval.
"""
import json
import httpx
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal
from app.models import Game, Team, OddsSnapshot
from app.config import settings

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_FILE = CACHE_DIR / "odds_latest.json"

# Sources we care about most (sharp books + major books)
PREFERRED_BOOKS = {"pinnacle", "bookmaker", "draftkings", "fanduel", "betmgm"}


def _cache_is_fresh() -> bool:
    """Check if cached odds are still within the fetch interval."""
    if not CACHE_FILE.exists():
        return False
    age_minutes = (datetime.utcnow().timestamp() - CACHE_FILE.stat().st_mtime) / 60
    return age_minutes < settings.odds_fetch_interval_minutes


def fetch_current_odds(force: bool = False):
    """Fetch current NFL odds and store snapshots.

    Uses disk cache to avoid redundant API calls. Pass force=True to bypass cache.
    """
    if not settings.odds_api_key:
        print("No ODDS_API_KEY set — skipping odds fetch")
        return

    CACHE_DIR.mkdir(exist_ok=True)

    if not force and _cache_is_fresh():
        print(f"Using cached odds (< {settings.odds_fetch_interval_minutes}m old)")
        events = json.loads(CACHE_FILE.read_text())
    else:
        resp = httpx.get(
            ODDS_API_URL,
            params={
                "apiKey": settings.odds_api_key,
                "regions": "us",
                "markets": "spreads,totals,h2h",
                "oddsFormat": "american",
            },
            timeout=30,
        )
        resp.raise_for_status()
        remaining = resp.headers.get("x-requests-remaining", "?")
        print(f"API call made. Requests remaining this month: {remaining}")
        events = resp.json()
        CACHE_FILE.write_text(json.dumps(events, indent=2))

    if not events:
        print("No events returned (NFL may be off-season)")
        return

    db = SessionLocal()
    try:

        teams_by_name = {}
        for team in db.query(Team).all():
            teams_by_name[team.name.lower()] = team
            # Also map common short forms
            teams_by_name[team.abbreviation.lower()] = team

        now = datetime.utcnow()
        added = 0

        for event in events:
            home_name = event.get("home_team", "").lower()
            away_name = event.get("away_team", "").lower()

            home_team = teams_by_name.get(home_name)
            away_team = teams_by_name.get(away_name)

            if not home_team or not away_team:
                # Try partial matching
                for key, team in teams_by_name.items():
                    if home_name and key in home_name:
                        home_team = team
                    if away_name and key in away_name:
                        away_team = team

            if not home_team or not away_team:
                continue

            # Find the game in our DB
            game = (
                db.query(Game)
                .filter(Game.home_team_id == home_team.id, Game.away_team_id == away_team.id, Game.season == settings.current_season)
                .first()
            )
            if not game:
                continue

            for bookmaker in event.get("bookmakers", []):
                book_key = bookmaker["key"]
                if book_key not in PREFERRED_BOOKS:
                    continue

                spread_home = None
                total = None
                ml_home = None
                ml_away = None

                for market in bookmaker.get("markets", []):
                    if market["key"] == "spreads":
                        for outcome in market["outcomes"]:
                            if outcome["name"].lower() in home_name or home_team.abbreviation.lower() in outcome["name"].lower():
                                spread_home = outcome.get("point")
                    elif market["key"] == "totals":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == "Over":
                                total = outcome.get("point")
                    elif market["key"] == "h2h":
                        for outcome in market["outcomes"]:
                            name_lower = outcome["name"].lower()
                            if name_lower in home_name or home_team.abbreviation.lower() in name_lower:
                                ml_home = outcome.get("price")
                            else:
                                ml_away = outcome.get("price")

                # Check if this is an opening line (first snapshot for this game+source)
                existing_count = (
                    db.query(OddsSnapshot)
                    .filter(OddsSnapshot.game_id == game.id, OddsSnapshot.source == book_key)
                    .count()
                )

                snapshot = OddsSnapshot(
                    game_id=game.id,
                    source=book_key,
                    spread_home=spread_home,
                    total=total,
                    moneyline_home=ml_home,
                    moneyline_away=ml_away,
                    is_opening=existing_count == 0,
                    captured_at=now,
                )
                db.add(snapshot)
                added += 1

        db.commit()
        print(f"Added {added} odds snapshots")
    finally:
        db.close()


if __name__ == "__main__":
    fetch_current_odds()
