"""Fetch NFL team statistics from ESPN's public API.

ESPN exposes two useful endpoints with no API key required:
  1. Team statistics  — per-team offensive + defensive season stats
  2. Standings        — W/L record, division rank, home/away splits

Both are cached to disk per (season, week). Stats don't change mid-week so
a cache that lasts until the next Sunday is appropriate; we use a configurable
TTL (default 24 hours) so a manual refresh is always possible.

Usage:
  python -m ingestion.team_stats_fetcher              # current season, current week
  python -m ingestion.team_stats_fetcher --week 8     # specific week
  python -m ingestion.team_stats_fetcher --force      # bypass cache
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.config import settings
from app.database import SessionLocal
from app.logging_config import setup_logging, get_logger
from app.models import Team
from app.models.team_stats import TeamStatSnapshot, TeamStanding
from ingestion.team_stats_normalizer import normalize_espn_team_stats, normalize_espn_standing

setup_logging()
logger = get_logger(__name__)

SOURCE = "espn"
CACHE_DIR = Path(__file__).parent / "cache"

# ESPN public endpoints — no key needed
ESPN_TEAM_STATS_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/statistics"
)
ESPN_STANDINGS_URL = (
    "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"
)
ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)

# ESPN's internal team IDs don't map 1:1 to our abbreviations.
# Built from ESPN scoreboard responses; keyed by our abbreviation.
ESPN_TEAM_ID_MAP: dict[str, str] = {
    "ARI": "22", "ATL": "1",  "BAL": "33", "BUF": "2",
    "CAR": "29", "CHI": "3",  "CIN": "4",  "CLE": "5",
    "DAL": "6",  "DEN": "7",  "DET": "8",  "GB": "9",
    "HOU": "34", "IND": "11", "JAX": "30", "KC": "12",
    "LAC": "24", "LAR": "14", "LV": "13",  "MIA": "15",
    "MIN": "16", "NE": "17",  "NO": "18",  "NYG": "19",
    "NYJ": "20", "PHI": "21", "PIT": "23", "SEA": "26",
    "SF": "25",  "TB": "27",  "TEN": "10", "WAS": "28",
}

# How long a cache file is considered fresh (in seconds)
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------

def _stats_cache_path(season: int, week: int, espn_team_id: str) -> Path:
    return CACHE_DIR / f"espn_team_stats_{season}_w{week}_{espn_team_id}.json"


def _standings_cache_path(season: int) -> Path:
    return CACHE_DIR / f"espn_standings_{season}.json"


def _is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age < CACHE_TTL_SECONDS


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _save_json(path: Path, data: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# ESPN API calls
# ---------------------------------------------------------------------------

def _fetch_team_stats_raw(espn_team_id: str, season: int, week: int, force: bool) -> dict:
    """Return raw ESPN team stats JSON, using disk cache when fresh."""
    cache = _stats_cache_path(season, week, espn_team_id)
    if not force and _is_fresh(cache):
        return _load_json(cache)

    resp = httpx.get(
        ESPN_TEAM_STATS_URL.format(team_id=espn_team_id),
        params={"season": season, "seasontype": 2},  # 2 = regular season
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _save_json(cache, data)
    return data


def _fetch_standings_raw(season: int, force: bool) -> dict:
    """Return raw ESPN standings JSON, using disk cache when fresh."""
    cache = _standings_cache_path(season)
    if not force and _is_fresh(cache):
        return _load_json(cache)

    resp = httpx.get(
        ESPN_STANDINGS_URL,
        params={"season": season, "seasontype": 2},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _save_json(cache, data)
    return data


def _current_week(season: int) -> int:
    """Ask the ESPN scoreboard what the current week is."""
    try:
        resp = httpx.get(
            ESPN_SCOREBOARD_URL,
            params={"dates": season, "seasontype": 2},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("week", {}).get("number", 1)
    except Exception:
        return 1


# ---------------------------------------------------------------------------
# Games played helpers
# ---------------------------------------------------------------------------

def _extract_categories(raw: dict) -> list[dict]:
    """Extract the stats categories list from the ESPN response.

    ESPN has used two layouts over time:
      - Legacy: raw['splits']['categories']
      - Current: raw['results']['stats']['categories']
    """
    cats = raw.get("splits", {}).get("categories", [])
    if cats:
        return cats
    return raw.get("results", {}).get("stats", {}).get("categories", [])


def _games_played_from_stats(raw: dict) -> int:
    """Extract the games played count from ESPN stats response."""
    for category in _extract_categories(raw):
        for stat in category.get("stats", []):
            if stat.get("name") in ("gamesPlayed", "teamGamesPlayed"):
                try:
                    return int(stat["value"])
                except (KeyError, TypeError, ValueError):
                    pass
    return 1  # safe fallback


# ---------------------------------------------------------------------------
# Main ingestion functions
# ---------------------------------------------------------------------------

def ingest_team_stats(season: int, week: int, force: bool = False) -> None:
    """Fetch and store stat snapshots for all 32 teams as of a given week."""
    db = SessionLocal()
    try:
        teams_by_abbr = {t.abbreviation: t for t in db.query(Team).all()}
        added = 0
        updated = 0
        errors = 0

        for abbr, team in teams_by_abbr.items():
            espn_id = ESPN_TEAM_ID_MAP.get(abbr)
            if not espn_id:
                logger.warning("No ESPN ID for %s — skipping", abbr)
                errors += 1
                continue

            try:
                raw = _fetch_team_stats_raw(espn_id, season, week, force)
            except httpx.HTTPError as exc:
                logger.error("HTTP error fetching stats for %s: %s", abbr, exc)
                errors += 1
                continue

            categories = _extract_categories(raw)
            if not categories:
                logger.warning("No stats categories for %s in ESPN response", abbr)
                errors += 1
                continue

            games_played = _games_played_from_stats(raw)
            normalized = normalize_espn_team_stats(categories, games_played)

            existing = (
                db.query(TeamStatSnapshot)
                .filter(
                    TeamStatSnapshot.team_id == team.id,
                    TeamStatSnapshot.season == season,
                    TeamStatSnapshot.week == week,
                    TeamStatSnapshot.source == SOURCE,
                )
                .first()
            )

            now = datetime.utcnow()
            if existing:
                for field, value in normalized.items():
                    setattr(existing, field, value)
                existing.fetched_at = now
                updated += 1
            else:
                snapshot = TeamStatSnapshot(
                    team_id=team.id,
                    season=season,
                    week=week,
                    source=SOURCE,
                    fetched_at=now,
                    **normalized,
                )
                db.add(snapshot)
                added += 1

        db.commit()
        logger.info(
            "Team stats (season=%d, week=%d): added=%d updated=%d errors=%d",
            season, week, added, updated, errors,
        )
    finally:
        db.close()


def ingest_standings(season: int, force: bool = False) -> None:
    """Fetch and upsert standings for all 32 teams."""
    db = SessionLocal()
    try:
        teams_by_abbr = {t.abbreviation: t for t in db.query(Team).all()}

        try:
            raw = _fetch_standings_raw(season, force)
        except httpx.HTTPError as exc:
            logger.error("HTTP error fetching standings: %s", exc)
            return

        # ESPN standings are nested: conferences -> divisions -> teams.
        # We walk the tree to assign division/conference rank as we go.
        added = 0
        updated = 0
        conf_rank_counter: dict[str, int] = {}  # conference name -> running rank

        groups = raw.get("children", [])  # AFC, NFC
        for conf_group in groups:
            conf_name = conf_group.get("name", "")
            conf_rank_counter[conf_name] = 0

            # ESPN uses two layouts:
            #   - Division-grouped: conf_group['children'] -> division groups -> entries
            #   - Flat per-conference: conf_group['standings']['entries']
            div_groups = conf_group.get("children", [])
            if div_groups:
                all_entries = []
                for div_group in div_groups:
                    entries = div_group.get("standings", {}).get("entries", [])
                    for div_rank, entry in enumerate(entries, start=1):
                        entry["_div_rank"] = div_rank
                        all_entries.append(entry)
            else:
                all_entries = conf_group.get("standings", {}).get("entries", [])
                for entry in all_entries:
                    entry["_div_rank"] = None

            for entry in all_entries:
                conf_rank_counter[conf_name] += 1
                conf_rank = conf_rank_counter[conf_name]

                # ESPN abbreviation is inside entry['team']['abbreviation']
                team_abbr = entry.get("team", {}).get("abbreviation", "")
                # ESPN sometimes uses different abbreviations
                team_abbr = {"WSH": "WAS", "JAX": "JAX"}.get(team_abbr, team_abbr)
                team = teams_by_abbr.get(team_abbr)
                if not team:
                    logger.warning("Unknown team abbreviation in standings: %r", team_abbr)
                    continue

                normalized = normalize_espn_standing(entry)
                div_rank = entry.pop("_div_rank", None)
                normalized["division_rank"] = div_rank
                normalized["conference_rank"] = conf_rank
                # Use ESPN's playoffSeed if available, else infer from conf rank
                seed_stat = next((s for s in entry.get("stats", []) if s.get("name") == "playoffSeed"), None)
                if seed_stat and seed_stat.get("value"):
                    normalized["playoff_seed"] = int(seed_stat["value"])
                else:
                    normalized["playoff_seed"] = conf_rank if conf_rank <= 7 else None

                now = datetime.utcnow()
                existing = (
                    db.query(TeamStanding)
                    .filter(
                        TeamStanding.team_id == team.id,
                        TeamStanding.season == season,
                        TeamStanding.source == SOURCE,
                    )
                    .first()
                )

                if existing:
                    for field, value in normalized.items():
                        setattr(existing, field, value)
                    existing.updated_at = now
                    updated += 1
                else:
                    standing = TeamStanding(
                        team_id=team.id,
                        season=season,
                        source=SOURCE,
                        updated_at=now,
                        **normalized,
                    )
                    db.add(standing)
                    added += 1

        db.commit()
        logger.info("Standings (season=%d): added=%d updated=%d", season, added, updated)
    finally:
        db.close()


def run(season: int | None = None, week: int | None = None, force: bool = False) -> None:
    """Convenience entry point: ingest both stats and standings."""
    season = season or settings.current_season
    week = week or _current_week(season)
    logger.info("Ingesting team stats for season=%d, week=%d", season, week)
    ingest_team_stats(season, week, force=force)
    ingest_standings(season, force=force)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch NFL team stats from ESPN")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Bypass disk cache")
    args = parser.parse_args()
    run(season=args.season, week=args.week, force=args.force)
