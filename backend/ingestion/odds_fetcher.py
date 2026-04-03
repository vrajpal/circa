"""Fetch odds from the-odds-api.com."""
import httpx
from datetime import datetime

from app.database import SessionLocal
from app.models import Game, Team, OddsSnapshot
from app.config import settings

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"

# Sources we care about most (sharp books + major books)
PREFERRED_BOOKS = {"pinnacle", "bookmaker", "draftkings", "fanduel", "betmgm"}


def fetch_current_odds():
    """Fetch current NFL odds and store snapshots."""
    if not settings.odds_api_key:
        print("No ODDS_API_KEY set — skipping odds fetch")
        return

    db = SessionLocal()
    try:
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
        events = resp.json()

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
