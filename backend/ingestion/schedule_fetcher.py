"""Fetch NFL schedule from ESPN's public API."""
import httpx
from datetime import datetime

from app.database import SessionLocal
from app.models import Game, Team
from app.config import settings

ESPN_SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

# ESPN week types: 1=preseason, 2=regular, 3=postseason
REGULAR_SEASON_TYPE = 2

# Known special slate dates (updated per season)
SPECIAL_SLATES = {
    2025: {
        "thanksgiving": ["2025-11-27"],
        "christmas": ["2025-12-25"],
    }
}


def get_slate(game_date: datetime, season: int) -> str:
    date_str = game_date.strftime("%Y-%m-%d")
    slates = SPECIAL_SLATES.get(season, {})
    for slate_name, dates in slates.items():
        if date_str in dates:
            return slate_name
    return "regular"


def fetch_week(season: int, week: int):
    """Fetch and store games for a specific week."""
    db = SessionLocal()
    try:
        resp = httpx.get(
            ESPN_SCHEDULE_URL,
            params={"dates": season, "seasontype": REGULAR_SEASON_TYPE, "week": week},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        teams_by_abbr = {t.abbreviation: t for t in db.query(Team).all()}
        # ESPN uses slightly different abbreviations for some teams
        abbr_map = {"WSH": "WAS", "JAX": "JAX", "LAR": "LAR"}

        events = data.get("events", [])
        added = 0

        for event in events:
            competition = event["competitions"][0]
            game_time = datetime.fromisoformat(event["date"].replace("Z", "+00:00"))

            home_data = next(c for c in competition["competitors"] if c["homeAway"] == "home")
            away_data = next(c for c in competition["competitors"] if c["homeAway"] == "away")

            home_abbr = abbr_map.get(home_data["team"]["abbreviation"], home_data["team"]["abbreviation"])
            away_abbr = abbr_map.get(away_data["team"]["abbreviation"], away_data["team"]["abbreviation"])

            home_team = teams_by_abbr.get(home_abbr)
            away_team = teams_by_abbr.get(away_abbr)

            if not home_team or not away_team:
                print(f"Skipping game: unknown team {home_abbr} or {away_abbr}")
                continue

            # Skip if already exists
            existing = (
                db.query(Game)
                .filter(Game.season == season, Game.week == week, Game.home_team_id == home_team.id, Game.away_team_id == away_team.id)
                .first()
            )
            if existing:
                continue

            game = Game(
                season=season,
                week=week,
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                game_time=game_time,
                slate=get_slate(game_time, season),
            )
            db.add(game)
            added += 1

        db.commit()
        print(f"Week {week}: added {added} games")
    finally:
        db.close()


def fetch_full_season(season: int = None):
    """Fetch all 18 weeks of the regular season."""
    season = season or settings.current_season
    for week in range(1, 19):
        fetch_week(season, week)


if __name__ == "__main__":
    from app.seed import seed_teams
    seed_teams()
    fetch_full_season()
