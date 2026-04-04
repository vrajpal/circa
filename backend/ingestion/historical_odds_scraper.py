"""Scrape historical NFL odds from sportsoddshistory.com.

Provides spreads and totals for completed games. No API key needed.
Results are cached to disk to avoid repeat requests.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from app.database import SessionLocal
from app.models import Game, Team, OddsSnapshot

CACHE_DIR = Path(__file__).parent / "cache"
SOURCE_NAME = "market_consensus"  # These are closing lines from the market

URL = "https://www.covers.com/sportsoddshistory/nfl-game-season/?y={season}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; circa-planner/1.0)"}


def _cache_path(season: int) -> Path:
    return CACHE_DIR / f"soh_{season}.html"


def _fetch_page(season: int) -> str:
    """Fetch the season page, using disk cache if available."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache = _cache_path(season)

    if cache.exists():
        print(f"Using cached HTML for {season}")
        return cache.read_text()

    print(f"Fetching covers.com/sportsoddshistory for {season}...")
    resp = httpx.get(URL.format(season=season), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    cache.write_text(resp.text)
    print(f"Cached to {cache}")
    return resp.text


def _parse_spread(cell_text: str) -> float | None:
    """Parse spread from text like 'L -8' or 'W -3.5' or 'P -7'."""
    match = re.search(r"[+-]?\d+\.?\d*", cell_text)
    return float(match.group()) if match else None


def _parse_total(cell_text: str) -> float | None:
    """Parse total from text like 'U 47.5' or 'O 51'."""
    match = re.search(r"\d+\.?\d*", cell_text)
    return float(match.group()) if match else None


# Map common name variations to our DB abbreviations
TEAM_NAME_MAP = {
    "arizona cardinals": "ARI",
    "atlanta falcons": "ATL",
    "baltimore ravens": "BAL",
    "buffalo bills": "BUF",
    "carolina panthers": "CAR",
    "chicago bears": "CHI",
    "cincinnati bengals": "CIN",
    "cleveland browns": "CLE",
    "dallas cowboys": "DAL",
    "denver broncos": "DEN",
    "detroit lions": "DET",
    "green bay packers": "GB",
    "houston texans": "HOU",
    "indianapolis colts": "IND",
    "jacksonville jaguars": "JAX",
    "kansas city chiefs": "KC",
    "los angeles chargers": "LAC",
    "los angeles rams": "LAR",
    "las vegas raiders": "LV",
    "miami dolphins": "MIA",
    "minnesota vikings": "MIN",
    "new england patriots": "NE",
    "new orleans saints": "NO",
    "new york giants": "NYG",
    "new york jets": "NYJ",
    "philadelphia eagles": "PHI",
    "pittsburgh steelers": "PIT",
    "seattle seahawks": "SEA",
    "san francisco 49ers": "SF",
    "tampa bay buccaneers": "TB",
    "tennessee titans": "TEN",
    "washington commanders": "WAS",
}


def _resolve_team(name: str, teams_by_abbr: dict) -> Team | None:
    abbr = TEAM_NAME_MAP.get(name.lower().strip())
    if abbr:
        return teams_by_abbr.get(abbr)
    return None


def parse_season(season: int) -> list[dict]:
    """Parse all games from the season page. Returns list of dicts with parsed data."""
    html = _fetch_page(season)
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table", class_="soh1")
    games = []

    # First 2 tables are summary (weekly ATS, team ATS). Game tables start at index 2.
    game_tables = tables[2:]

    for week_num, table in enumerate(game_tables, start=1):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 10:
                continue

            # Favorite is in cell 4, underdog in cell 8
            fav_link = cells[4].find("a")
            dog_link = cells[8].find("a")
            if not fav_link or not dog_link:
                continue

            fav_name = fav_link.get_text(strip=True)
            dog_name = dog_link.get_text(strip=True)

            date_str = cells[1].get_text(strip=True)
            fav_location = cells[3].get_text(strip=True)   # "@" = fav is away, "" = fav is home
            dog_location = cells[7].get_text(strip=True)    # "@" = dog is away

            spread_text = cells[6].get_text(strip=True)
            total_text = cells[9].get_text(strip=True)

            spread = _parse_spread(spread_text)
            total = _parse_total(total_text)

            # Determine home/away:
            # Col 3 "@" means favorite is away (traveling to underdog's home)
            # Col 3 ""  means favorite is home
            # Col 3 "N" means neutral site
            if fav_location == "@":
                home_name = dog_name
                away_name = fav_name
                # Spread is always the favorite's line (negative). Home is the dog.
                home_spread = -spread if spread is not None else None
            else:
                home_name = fav_name
                away_name = dog_name
                # Favorite is home, spread is already their line
                home_spread = spread

            games.append({
                "week": week_num,
                "date_str": date_str,
                "home_name": home_name,
                "away_name": away_name,
                "spread_home": home_spread,
                "total": total,
            })

    return games


def ingest_season(season: int = 2025):
    """Parse and store historical odds for a season."""
    parsed = parse_season(season)
    print(f"Parsed {len(parsed)} games from sportsoddshistory.com")

    db = SessionLocal()
    try:
        teams_by_abbr = {t.abbreviation: t for t in db.query(Team).all()}
        added = 0
        skipped = 0

        for g in parsed:
            home_team = _resolve_team(g["home_name"], teams_by_abbr)
            away_team = _resolve_team(g["away_name"], teams_by_abbr)

            if not home_team or not away_team:
                print(f"  Could not resolve: {g['home_name']} vs {g['away_name']}")
                skipped += 1
                continue

            # Find matching game in DB — match either orientation since
            # the scraper's home/away may not align with ESPN's
            team_a, team_b = home_team, away_team
            game = (
                db.query(Game)
                .filter(
                    Game.season == season,
                    Game.week == g["week"],
                )
                .filter(
                    ((Game.home_team_id == team_a.id) & (Game.away_team_id == team_b.id))
                    | ((Game.home_team_id == team_b.id) & (Game.away_team_id == team_a.id))
                )
                .first()
            )

            if not game:
                skipped += 1
                continue

            # Recompute spread relative to the DB's home team
            if g["spread_home"] is not None:
                if game.home_team_id == home_team.id:
                    spread_home = g["spread_home"]
                else:
                    # Our "home" was actually the away team in the DB — flip the spread
                    spread_home = -g["spread_home"]
            else:
                spread_home = None

            # Skip if we already have odds for this game from this source
            existing = (
                db.query(OddsSnapshot)
                .filter(OddsSnapshot.game_id == game.id, OddsSnapshot.source == SOURCE_NAME)
                .first()
            )
            if existing:
                continue

            snapshot = OddsSnapshot(
                game_id=game.id,
                source=SOURCE_NAME,
                spread_home=spread_home,
                total=g["total"],
                moneyline_home=None,
                moneyline_away=None,
                is_opening=False,  # These are closing lines
                captured_at=game.game_time,  # Use game time as the snapshot time
            )
            db.add(snapshot)
            added += 1

        db.commit()
        print(f"Added {added} odds snapshots, skipped {skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    ingest_season(2025)
