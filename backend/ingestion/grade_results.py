"""Grade a completed (or in-progress) season.

Three idempotent stages, run in order:

  1. grade_games    — one GameResult per game that has a final score and a real
                      closing line (odds_snapshots.line_type == 'closing').
  2. grade_picks    — set result/graded_at on Pick and ConsensusPick rows.
  3. compute_form   — roll GameResults up into per-team ATS and O/U records on
                      TeamStanding.

Grading is always done against the *real* closing line, never the synthetic
line-movement snapshots. Re-running is safe: each stage upserts.

Usage:
  python -m ingestion.grade_results                 # current season
  python -m ingestion.grade_results --season 2025
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime

from app.config import settings
from app.database import SessionLocal
from app.models import (
    Game,
    GameResult,
    OddsSnapshot,
    Pick,
    ConsensusPick,
    TeamStanding,
    IngestionRun,
)
from app.services.grading import grade_game, grade_ats_pick, grade_survivor_pick, HOME, AWAY

STANDINGS_SOURCE = "espn"  # ATS/OU records attach to the team's standing row


@contextmanager
def _run(db, source: str, season: int):
    """Record an IngestionRun row around a stage; capture row count and errors."""
    run = IngestionRun(source=source, season=season, status="running", started_at=datetime.utcnow())
    db.add(run)
    db.commit()
    counter = {"rows": 0}
    try:
        yield counter
        run.status = "success"
    except Exception as exc:  # noqa: BLE001 — recorded on the run row, then re-raised
        # The stage's transaction is poisoned; roll it back so the audit-row
        # update below commits on a clean session instead of silently failing.
        db.rollback()
        run.status = "error"
        run.error = str(exc)[:2000]
        raise
    finally:
        # run may have been expired by the rollback above; merge it back so the
        # status/row-count update reliably persists either way.
        run = db.merge(run)
        run.rows_written = counter["rows"]
        run.finished_at = datetime.utcnow()
        db.commit()


def _closing_lines(db, season: int) -> dict[int, OddsSnapshot]:
    """game_id -> the real closing-line snapshot for that game."""
    rows = (
        db.query(OddsSnapshot)
        .join(Game, Game.id == OddsSnapshot.game_id)
        .filter(Game.season == season, OddsSnapshot.line_type == "closing")
        .all()
    )
    return {s.game_id: s for s in rows}


# ---------------------------------------------------------------------------
# Stage 1: games
# ---------------------------------------------------------------------------

def grade_games(db, season: int) -> int:
    closing = _closing_lines(db, season)
    existing = {gr.game_id: gr for gr in db.query(GameResult).join(
        Game, Game.id == GameResult.game_id).filter(Game.season == season).all()}

    graded = 0
    for game in db.query(Game).filter(Game.season == season).all():
        snap = closing.get(game.id)
        spread = snap.spread_home if snap else None
        total = snap.total if snap else None
        grade = grade_game(game.score_home, game.score_away, spread, total)
        if grade is None:
            continue  # no final score yet

        def side_to_team(side: str | None) -> int | None:
            if side == HOME:
                return game.home_team_id
            if side == AWAY:
                return game.away_team_id
            return None

        gr = existing.get(game.id) or GameResult(game_id=game.id)
        gr.graded_against_snapshot_id = snap.id if snap else None
        gr.closing_spread_home = spread
        gr.closing_total = total
        gr.su_winner_team_id = side_to_team(grade.su_winner)
        gr.ats_winner_team_id = side_to_team(grade.ats_winner)
        gr.ats_margin_home = grade.ats_margin_home
        gr.total_result = grade.total_result
        gr.graded_at = datetime.utcnow()
        if gr.id is None:
            db.add(gr)
        graded += 1

    db.commit()
    return graded


# ---------------------------------------------------------------------------
# Stage 2: picks
# ---------------------------------------------------------------------------

def _grade_pick_rows(db, season: int, model) -> int:
    results = {gr.game_id: gr for gr in db.query(GameResult).join(
        Game, Game.id == GameResult.game_id).filter(Game.season == season).all()}
    games = {g.id: g for g in db.query(Game).filter(Game.season == season).all()}

    graded = 0
    rows = db.query(model).filter(model.season == season).all()
    for pick in rows:
        game = games.get(pick.game_id) if pick.game_id else None
        gr = results.get(pick.game_id) if pick.game_id else None
        if game is None or gr is None:
            continue
        picked_side = HOME if pick.picked_team_id == game.home_team_id else AWAY

        from app.services.grading import GameGrade
        grade = GameGrade(
            su_winner=(HOME if gr.su_winner_team_id == game.home_team_id
                       else AWAY if gr.su_winner_team_id == game.away_team_id else None),
            ats_winner=(HOME if gr.ats_winner_team_id == game.home_team_id
                        else AWAY if gr.ats_winner_team_id == game.away_team_id else None),
            ats_margin_home=gr.ats_margin_home,
            total_result=gr.total_result,
        )

        if pick.contest_type == "survivor":
            result = grade_survivor_pick(picked_side, grade)
        else:  # millions / ATS
            result = grade_ats_pick(picked_side, grade)
        if result is None:
            continue  # no line to grade against; leave pending

        pick.result = result
        pick.graded_against_snapshot_id = gr.graded_against_snapshot_id
        pick.graded_at = datetime.utcnow()
        graded += 1

    db.commit()
    return graded


def grade_picks(db, season: int) -> int:
    return _grade_pick_rows(db, season, Pick) + _grade_pick_rows(db, season, ConsensusPick)


# ---------------------------------------------------------------------------
# Stage 3: team ATS / O/U form
# ---------------------------------------------------------------------------

def compute_form(db, season: int) -> int:
    games = {g.id: g for g in db.query(Game).filter(Game.season == season).all()}

    # team_id -> tallies
    blank = lambda: {"ats_w": 0, "ats_l": 0, "ats_p": 0, "ou_o": 0, "ou_u": 0, "ou_p": 0}
    tally: dict[int, dict] = {}

    for gr in db.query(GameResult).join(Game, Game.id == GameResult.game_id).filter(
        Game.season == season
    ).all():
        game = games[gr.game_id]
        home, away = game.home_team_id, game.away_team_id
        tally.setdefault(home, blank())
        tally.setdefault(away, blank())

        # ATS — only when there was a spread
        if gr.ats_margin_home is not None:
            if gr.ats_winner_team_id is None:  # push
                tally[home]["ats_p"] += 1
                tally[away]["ats_p"] += 1
            elif gr.ats_winner_team_id == home:
                tally[home]["ats_w"] += 1
                tally[away]["ats_l"] += 1
            else:
                tally[away]["ats_w"] += 1
                tally[home]["ats_l"] += 1

        # O/U — both teams share the game's total result
        if gr.total_result == "over":
            tally[home]["ou_o"] += 1
            tally[away]["ou_o"] += 1
        elif gr.total_result == "under":
            tally[home]["ou_u"] += 1
            tally[away]["ou_u"] += 1
        elif gr.total_result == "push":
            tally[home]["ou_p"] += 1
            tally[away]["ou_p"] += 1

    standings = {s.team_id: s for s in db.query(TeamStanding).filter(
        TeamStanding.season == season, TeamStanding.source == STANDINGS_SOURCE).all()}

    updated = 0
    for team_id, t in tally.items():
        s = standings.get(team_id)
        if s is None:
            # No standing row (e.g. stats weren't ingested). Create a minimal one
            # so the ATS/OU form isn't lost.
            s = TeamStanding(team_id=team_id, season=season, source=STANDINGS_SOURCE)
            db.add(s)
        s.ats_wins, s.ats_losses, s.ats_pushes = t["ats_w"], t["ats_l"], t["ats_p"]
        s.ou_overs, s.ou_unders, s.ou_pushes = t["ou_o"], t["ou_u"], t["ou_p"]
        s.updated_at = datetime.utcnow()
        updated += 1

    db.commit()
    return updated


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def grade_season(season: int) -> None:
    db = SessionLocal()
    try:
        with _run(db, "grade_games", season) as c:
            c["rows"] = grade_games(db, season)
            print(f"  grade_games: {c['rows']} games graded")
        with _run(db, "grade_picks", season) as c:
            c["rows"] = grade_picks(db, season)
            print(f"  grade_picks: {c['rows']} picks graded")
        with _run(db, "compute_form", season) as c:
            c["rows"] = compute_form(db, season)
            print(f"  compute_form: {c['rows']} team records updated")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade a season's games and picks.")
    parser.add_argument("--season", type=int, default=settings.current_season)
    args = parser.parse_args()
    print(f"Grading season {args.season}...")
    grade_season(args.season)
    print("Done.")


if __name__ == "__main__":
    main()
