"""Backfill a completed NFL season with scores, odds, stats, and standings.

Pulls from:
  - ESPN scoreboard: final scores for all games
  - Covers.com: closing line spreads and totals
  - ESPN team stats: week-by-week stat snapshots for all 32 teams
  - ESPN standings: final season standings

For line movement, we synthesize realistic snapshots between opening and
closing lines. Real line movement is lost once a game completes, but we can
reconstruct the general shape: opening line → mid-week drift → closing line.

Usage:
  python -m ingestion.backfill_season                    # defaults to 2025
  python -m ingestion.backfill_season --season 2024
  python -m ingestion.backfill_season --scores-only      # just scores
  python -m ingestion.backfill_season --force             # bypass cache
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.database import SessionLocal
from app.logging_config import setup_logging, get_logger
from app.models import Game, Team

setup_logging()
logger = get_logger(__name__)
from app.models.odds import OddsSnapshot
from app.models.team_stats import TeamStatSnapshot, TeamStanding
from ingestion.historical_odds_scraper import parse_season as parse_closing_lines
from ingestion.team_stats_fetcher import (
    ingest_team_stats,
    ingest_standings,
    _fetch_team_stats_raw,
    _extract_categories,
    _games_played_from_stats,
    ESPN_TEAM_ID_MAP,
)
from ingestion.team_stats_normalizer import normalize_espn_team_stats

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)


# ---------------------------------------------------------------------------
# 1. Scores from ESPN
# ---------------------------------------------------------------------------

def backfill_scores(season: int) -> None:
    """Fetch final scores from ESPN and update Game rows."""
    db = SessionLocal()
    try:
        teams_by_abbr = {t.abbreviation: t for t in db.query(Team).all()}
        updated = 0

        for week in range(1, 19):
            resp = httpx.get(
                ESPN_SCOREBOARD_URL,
                params={"dates": season, "seasontype": 2, "week": week},
                timeout=30,
            )
            resp.raise_for_status()
            events = resp.json().get("events", [])

            for event in events:
                comp = event["competitions"][0]
                scores = {}
                for competitor in comp["competitors"]:
                    abbr = competitor["team"]["abbreviation"]
                    abbr = {"WSH": "WAS"}.get(abbr, abbr)
                    ha = competitor["homeAway"]
                    scores[ha] = {"abbr": abbr, "score": int(competitor.get("score", 0))}

                if "home" not in scores or "away" not in scores:
                    continue

                home_team = teams_by_abbr.get(scores["home"]["abbr"])
                away_team = teams_by_abbr.get(scores["away"]["abbr"])
                if not home_team or not away_team:
                    continue

                game = (
                    db.query(Game)
                    .filter(
                        Game.season == season,
                        Game.week == week,
                        Game.home_team_id == home_team.id,
                        Game.away_team_id == away_team.id,
                    )
                    .first()
                )
                if game:
                    game.score_home = scores["home"]["score"]
                    game.score_away = scores["away"]["score"]
                    updated += 1

            logger.info("Scores: week %d — %d games", week, len(events))

        db.commit()
        logger.info("Scores: updated %d games", updated)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2. Closing lines from Covers.com
# ---------------------------------------------------------------------------

def backfill_closing_lines(season: int) -> None:
    """Ingest closing lines from covers.com historical scraper."""
    from ingestion.historical_odds_scraper import ingest_season
    ingest_season(season)


# ---------------------------------------------------------------------------
# 3. Synthesized line movement
# ---------------------------------------------------------------------------

SYNTHETIC_BOOKS = ["pinnacle", "draftkings", "fanduel"]
NUM_SNAPSHOTS_PER_BOOK = 6  # opening + 4 mid-week + closing


def _spread_to_moneyline(spread: float) -> tuple[int, int]:
    """Rough spread-to-moneyline conversion for realism."""
    if spread == 0:
        return -110, -110
    # Each point of spread ≈ 30 moneyline points (rough NFL heuristic)
    if spread < 0:  # home is favored
        fav_ml = int(-110 - abs(spread) * 30)
        dog_ml = int(100 + abs(spread) * 25)
        return max(fav_ml, -1000), min(dog_ml, 900)
    else:  # home is underdog
        dog_ml = int(100 + abs(spread) * 25)
        fav_ml = int(-110 - abs(spread) * 30)
        return min(dog_ml, 900), max(fav_ml, -1000)


def _jitter(value: float, max_delta: float = 0.5) -> float:
    """Add small random noise, snapping to 0.5-point increments."""
    delta = random.uniform(-max_delta, max_delta)
    return round((value + delta) * 2) / 2


def synthesize_line_movement(season: int) -> None:
    """Generate realistic intermediate odds snapshots between opening and closing.

    For each game, creates snapshots at:
      - Opening (game_time - 7 days)
      - 4 intermediate points showing gradual drift
      - Closing (game_time - 1 hour)

    The line drifts from opening toward closing with small random jitter
    to simulate real market movement.
    """
    db = SessionLocal()
    try:
        games = db.query(Game).filter(Game.season == season).all()

        # Build lookup: game_id -> existing snapshots
        existing_by_game: dict[int, list[OddsSnapshot]] = {}
        for snap in db.query(OddsSnapshot).filter(
            OddsSnapshot.game_id.in_([g.id for g in games])
        ).all():
            existing_by_game.setdefault(snap.game_id, []).append(snap)

        # Build closing line lookup from covers data
        closing_by_game: dict[int, dict] = {}
        for snap_list in existing_by_game.values():
            for s in snap_list:
                if s.source == "market_consensus":
                    closing_by_game[s.game_id] = {
                        "spread": s.spread_home,
                        "total": s.total,
                    }

        added = 0
        for game in games:
            # Get opening line (any existing is_opening snapshot)
            existing = existing_by_game.get(game.id, [])
            opening_snap = next((s for s in existing if s.is_opening), None)
            closing_data = closing_by_game.get(game.id)

            # Skip if we already have synthetic movement (>3 snapshots per book)
            book_counts = {}
            for s in existing:
                if s.source in SYNTHETIC_BOOKS:
                    book_counts[s.source] = book_counts.get(s.source, 0) + 1
            if any(c >= NUM_SNAPSHOTS_PER_BOOK for c in book_counts.values()):
                continue

            # Determine opening and closing values
            if opening_snap:
                open_spread = opening_snap.spread_home
                open_total = opening_snap.total
            elif closing_data:
                # No opening line — use closing with some offset as a proxy
                open_spread = _jitter(closing_data["spread"], 1.5) if closing_data["spread"] is not None else None
                open_total = _jitter(closing_data["total"], 1.5) if closing_data["total"] is not None else None
            else:
                continue  # No data at all for this game

            close_spread = closing_data["spread"] if closing_data else open_spread
            close_total = closing_data["total"] if closing_data else open_total

            if open_spread is None and close_spread is None:
                continue

            game_time = game.game_time
            if not game_time:
                continue

            # Generate timestamps: opening = 7 days before, closing = 1 hour before
            open_time = game_time - timedelta(days=7)
            close_time = game_time - timedelta(hours=1)
            interval = (close_time - open_time) / (NUM_SNAPSHOTS_PER_BOOK - 1)

            for book in SYNTHETIC_BOOKS:
                # Small per-book offset so lines aren't identical
                book_offset = random.uniform(-0.5, 0.5)
                book_total_offset = random.uniform(-0.5, 0.5)

                for i in range(NUM_SNAPSHOTS_PER_BOOK):
                    t = i / (NUM_SNAPSHOTS_PER_BOOK - 1)  # 0.0 → 1.0
                    timestamp = open_time + interval * i

                    # Interpolate with jitter
                    if open_spread is not None and close_spread is not None:
                        base_spread = open_spread + (close_spread - open_spread) * t
                        spread = round((base_spread + book_offset + random.uniform(-0.3, 0.3)) * 2) / 2
                    else:
                        spread = None

                    if open_total is not None and close_total is not None:
                        base_total = open_total + (close_total - open_total) * t
                        total = round((base_total + book_total_offset + random.uniform(-0.3, 0.3)) * 2) / 2
                    else:
                        total = None

                    ml_home, ml_away = _spread_to_moneyline(spread) if spread is not None else (None, None)

                    snapshot = OddsSnapshot(
                        game_id=game.id,
                        source=book,
                        spread_home=spread,
                        total=total,
                        moneyline_home=ml_home,
                        moneyline_away=ml_away,
                        is_opening=(i == 0),
                        captured_at=timestamp,
                    )
                    db.add(snapshot)
                    added += 1

        db.commit()
        logger.info("Line movement: synthesized %d snapshots across %d games", added, len(games))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Team stats for all 18 weeks
# ---------------------------------------------------------------------------

def backfill_team_stats(season: int, force: bool = False) -> None:
    """Ingest team stats for every week of the season."""
    for week in range(1, 19):
        logger.info("Ingesting stats for week %d", week)
        ingest_team_stats(season, week, force=force)


def backfill_standings(season: int, force: bool = False) -> None:
    """Ingest final season standings."""
    ingest_standings(season, force=force)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(
    season: int | None = None,
    scores_only: bool = False,
    force: bool = False,
) -> None:
    season = season or settings.current_season

    logger.info("=== Backfilling %d NFL season ===", season)

    logger.info("[1/5] Backfilling scores from ESPN")
    backfill_scores(season)

    if scores_only:
        logger.info("Done (scores only)")
        return

    logger.info("[2/5] Backfilling closing lines from Covers.com")
    backfill_closing_lines(season)

    logger.info("[3/5] Synthesizing line movement")
    random.seed(season)  # Deterministic for reproducibility
    synthesize_line_movement(season)

    logger.info("[4/5] Backfilling team stats (all 18 weeks)")
    backfill_team_stats(season, force=force)

    logger.info("[5/5] Backfilling standings")
    backfill_standings(season, force=force)

    logger.info("=== Backfill complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill a completed NFL season")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--scores-only", action="store_true")
    parser.add_argument("--force", action="store_true", help="Bypass cache for stats")
    args = parser.parse_args()
    run(season=args.season, scores_only=args.scores_only, force=args.force)
