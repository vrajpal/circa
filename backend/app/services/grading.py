"""Pure grading logic for completed games and contest picks.

No DB, no network — just the math that turns a final score and a closing line
into outcomes. Keeping it pure means it can be unit-tested exhaustively (every
push / tie / no-line edge case) without fixtures, and reused both by the batch
grading stage (ingestion/grade_results.py) and by any live in-season grading.

Convention: spreads are stored "home perspective" (spread_home). A favourite
lays points, so a home favourite has a negative spread_home.
"""
from __future__ import annotations

from dataclasses import dataclass


# Sentinels for the "side" of an outcome.
HOME = "home"
AWAY = "away"
PUSH = "push"


@dataclass
class GameGrade:
    """Outcome of a single game against its closing line.

    Any field is None when it can't be determined (e.g. ats_* when no spread
    was available). su_winner / ats_winner are HOME, AWAY, or None. None for
    su_winner means a tie; None for ats_winner means a push *iff* ats_margin_home
    is not None — callers should check ats_margin_home to disambiguate
    "push" from "no line".
    """
    su_winner: str | None
    ats_winner: str | None
    ats_margin_home: float | None
    total_result: str | None  # "over" / "under" / "push" / None


def grade_game(
    score_home: int | None,
    score_away: int | None,
    spread_home: float | None,
    total: float | None,
) -> GameGrade | None:
    """Grade one game. Returns None if the game has no final score yet."""
    if score_home is None or score_away is None:
        return None

    margin_home = score_home - score_away

    # Straight up
    if margin_home > 0:
        su_winner = HOME
    elif margin_home < 0:
        su_winner = AWAY
    else:
        su_winner = None  # tie

    # Against the spread
    ats_winner: str | None = None
    ats_margin_home: float | None = None
    if spread_home is not None:
        ats_margin_home = margin_home + spread_home
        if ats_margin_home > 0:
            ats_winner = HOME
        elif ats_margin_home < 0:
            ats_winner = AWAY
        else:
            ats_winner = None  # push (disambiguated by ats_margin_home == 0)

    # Total
    total_result: str | None = None
    if total is not None:
        combined = score_home + score_away
        if combined > total:
            total_result = "over"
        elif combined < total:
            total_result = "under"
        else:
            total_result = PUSH

    return GameGrade(
        su_winner=su_winner,
        ats_winner=ats_winner,
        ats_margin_home=ats_margin_home,
        total_result=total_result,
    )


def grade_ats_pick(picked_side: str, grade: GameGrade) -> str | None:
    """Grade an against-the-spread (Millions) pick.

    picked_side is HOME or AWAY. Returns "win" / "loss" / "push", or None if
    the game had no spread to grade against (caller should leave it pending).
    """
    if grade.ats_margin_home is None:
        return None
    if grade.ats_winner is None:  # margin == 0 -> push
        return PUSH
    return "win" if picked_side == grade.ats_winner else "loss"


def grade_survivor_pick(picked_side: str, grade: GameGrade) -> str:
    """Grade a straight-up (Survivor) pick.

    picked_side is HOME or AWAY. A tie returns "push"; in most survivor formats
    a tie eliminates, but we record it neutrally and let the contest layer decide.
    """
    if grade.su_winner is None:  # tie
        return PUSH
    return "win" if picked_side == grade.su_winner else "loss"
