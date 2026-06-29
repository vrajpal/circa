"""Fill derived moneylines onto real closing-line snapshots.

The historical odds source gives us closing spreads and totals but no
moneyline. For survivor win-probability context we derive a fair (no-vig)
moneyline from the closing spread and store it on the same snapshot, tagged
moneyline_derived=True so it's never mistaken for a real market price.

Idempotent: only fills snapshots whose moneyline is missing or already marked
derived; real book moneylines (moneyline_derived=False with a value) are never
overwritten.

Usage:
  python -m ingestion.derive_moneylines                 # current season
  python -m ingestion.derive_moneylines --season 2025
"""
from __future__ import annotations

import argparse
from datetime import datetime

from app.config import settings
from app.database import SessionLocal
from app.models import Game, OddsSnapshot, IngestionRun
from app.services.odds_pricing import spread_to_moneyline


def derive_for_season(season: int) -> int:
    db = SessionLocal()
    run = IngestionRun(source="derive_moneylines", season=season, status="running",
                       started_at=datetime.utcnow())
    db.add(run)
    db.commit()
    filled = 0
    try:
        snaps = (
            db.query(OddsSnapshot)
            .join(Game, Game.id == OddsSnapshot.game_id)
            .filter(Game.season == season, OddsSnapshot.line_type == "closing")
            .all()
        )
        for snap in snaps:
            if snap.spread_home is None:
                continue
            # Don't clobber a real book moneyline.
            if snap.moneyline_home is not None and not snap.moneyline_derived:
                continue
            home_ml, away_ml = spread_to_moneyline(snap.spread_home)
            snap.moneyline_home = home_ml
            snap.moneyline_away = away_ml
            snap.moneyline_derived = True
            filled += 1
        db.commit()
        run.status = "success"
        print(f"  derive_moneylines: filled {filled} closing snapshots")
    except Exception as exc:  # noqa: BLE001
        run.status = "error"
        run.error = str(exc)[:2000]
        raise
    finally:
        run.rows_written = filled
        run.finished_at = datetime.utcnow()
        db.commit()
        db.close()
    return filled


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive fair moneylines from closing spreads.")
    parser.add_argument("--season", type=int, default=settings.current_season)
    args = parser.parse_args()
    print(f"Deriving moneylines for season {args.season}...")
    derive_for_season(args.season)
    print("Done.")


if __name__ == "__main__":
    main()
