"""Normalize raw team stat payloads from different sources into a unified dict.

Each source has its own field names and units. This module is the single place
where that mapping lives. The output is always a plain dict whose keys match
the columns on TeamStatSnapshot and TeamStanding.

Why a separate module: the fetchers focus on network + caching; the normalizer
focuses on correctness of field mapping. Keeping them separate means you can
unit-test normalization without needing a live API or DB.

Currently supported sources
  - espn_stats   : raw "statistics" array from ESPN team stats endpoint
  - espn_standings: raw entry from ESPN standings endpoint
"""
from __future__ import annotations


def normalize_espn_team_stats(raw_stats: list[dict], games_played: int) -> dict:
    """Map ESPN's flat stats array to our unified schema.

    ESPN returns a list of category objects, each with a 'stats' list of
    individual stat entries keyed by 'name'. We build a flat lookup then
    pull values by name.

    Args:
        raw_stats: the 'splits.categories' list from the ESPN team stats API.
        games_played: number of games so we can compute per-game rates for
                      stats that ESPN returns as season totals.

    Returns:
        Dict with keys matching TeamStatSnapshot columns. Missing values are None.
    """
    # Flatten all stats into a single name -> value dict
    lookup: dict[str, float] = {}
    for category in raw_stats:
        for stat in category.get("stats", []):
            name = stat.get("name")
            value = stat.get("value")
            if name and value is not None:
                try:
                    lookup[name] = float(value)
                except (TypeError, ValueError):
                    pass

    gp = max(games_played, 1)  # guard against division-by-zero in week 0

    def per_game(key: str) -> float | None:
        val = lookup.get(key)
        return round(val / gp, 2) if val is not None else None

    def direct(key: str) -> float | None:
        val = lookup.get(key)
        return round(val, 2) if val is not None else None

    def pct(numerator_key: str, denominator_key: str) -> float | None:
        num = lookup.get(numerator_key)
        den = lookup.get(denominator_key)
        if num is not None and den and den > 0:
            return round(num / den * 100, 1)
        return None

    # Red zone: ESPN uses 'redZoneTouchdowns' and 'redZoneAttempts'
    rz_attempts_raw = lookup.get("redZoneAttempts")
    rz_tds_raw = lookup.get("redZoneTouchdowns")
    rz_td_pct = None
    if rz_tds_raw is not None and rz_attempts_raw and rz_attempts_raw > 0:
        rz_td_pct = round(rz_tds_raw / rz_attempts_raw * 100, 1)

    # Third down: ESPN uses 'thirdDownConversions' and 'thirdDownAttempts'
    third_pct = pct("thirdDownConversions", "thirdDownAttempts")

    # Points: ESPN has 'totalPointsPerGame' for offensive and a separate
    # defensive category. Fall back to computing from totals if needed.
    off_ppg = direct("totalPointsPerGame") or per_game("totalPoints")
    # Defensive points allowed: ESPN puts this in a 'scoring' category
    # on the defensive side; it may come in as 'pointsAllowed'
    def_ppg = direct("pointsAllowedPerGame") or per_game("pointsAllowed")

    off_ypg = direct("totalYardsPerGame") or per_game("totalYards")
    pass_ypg = direct("passingYardsPerGame") or per_game("netPassingYards")
    rush_ypg = direct("rushingYardsPerGame") or per_game("rushingYards")

    def_ypg = direct("yardsAllowedPerGame") or per_game("yardsAllowed")
    def_pass_ypg = (
        direct("passingYardsAllowedPerGame") or per_game("passingYardsAllowed")
    )
    def_rush_ypg = (
        direct("rushingYardsAllowedPerGame") or per_game("rushingYardsAllowed")
    )

    sacks_pg = per_game("sacks")
    takeaways_pg = per_game("interceptions")  # ESPN uses interceptions here;
    # turnovers forced = INT + fumbles recovered, but ESPN splits these
    fumbles_recovered = lookup.get("fumblesRecovered", 0.0)
    interceptions = lookup.get("interceptions", 0.0)
    takeaways_total = interceptions + fumbles_recovered
    takeaways_pg = round(takeaways_total / gp, 2) if takeaways_total else None

    turnovers_total = lookup.get("turnovers") or (
        (lookup.get("fumblesLost", 0) or 0) + (lookup.get("interceptionsThrown", 0) or 0)
    )
    turnovers_pg = round(turnovers_total / gp, 2) if turnovers_total else None

    pt_diff_pg = None
    if off_ppg is not None and def_ppg is not None:
        pt_diff_pg = round(off_ppg - def_ppg, 2)

    return {
        "games_played": games_played,
        "points_per_game": off_ppg,
        "total_yards_per_game": off_ypg,
        "passing_yards_per_game": pass_ypg,
        "rushing_yards_per_game": rush_ypg,
        "turnovers_per_game": turnovers_pg,
        "red_zone_attempts": int(rz_attempts_raw) if rz_attempts_raw is not None else None,
        "red_zone_td_pct": rz_td_pct,
        "third_down_pct": third_pct,
        "points_allowed_per_game": def_ppg,
        "yards_allowed_per_game": def_ypg,
        "passing_yards_allowed_per_game": def_pass_ypg,
        "rushing_yards_allowed_per_game": def_rush_ypg,
        "sacks_per_game": sacks_pg,
        "takeaways_per_game": takeaways_pg,
        "point_differential_per_game": pt_diff_pg,
    }


def normalize_espn_standing(entry: dict) -> dict:
    """Map a single ESPN standings entry to our TeamStanding columns.

    ESPN returns standings as a list of team entries. Each entry has a 'stats'
    array and 'team' info. The caller is responsible for resolving team_id.

    Args:
        entry: one item from the ESPN standings 'entries' array.

    Returns:
        Dict with keys matching TeamStanding columns (excluding team_id/season/source).
    """
    # Build lookup from the stats array
    lookup: dict[str, float | str] = {}
    for stat in entry.get("stats", []):
        name = stat.get("name")
        # ESPN standings use 'value' for numeric and 'displayValue' for formatted strings
        value = stat.get("value")
        display = stat.get("displayValue", "")
        if name:
            if value is not None:
                try:
                    lookup[name] = float(value)
                except (TypeError, ValueError):
                    lookup[name] = display
            else:
                lookup[name] = display

    def _int(key: str) -> int | None:
        val = lookup.get(key)
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    def _float(key: str) -> float | None:
        val = lookup.get(key)
        try:
            return round(float(val), 3) if val is not None else None
        except (TypeError, ValueError):
            return None

    wins = _int("wins")
    losses = _int("losses")
    ties = _int("ties")
    win_pct = _float("winPercent")

    # Home/away splits: ESPN uses 'homeWins'/'homeLosses'/'roadWins'/'roadLosses'
    home_wins = _int("homeWins")
    home_losses = _int("homeLosses")
    away_wins = _int("roadWins")
    away_losses = _int("roadLosses")

    # Division/conference rank and playoff seeding come from the parent group
    # context, not the entry itself. The caller should pass these in via the
    # supplemental dict if available, so we default to None here.
    return {
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_pct": win_pct,
        "division_rank": None,      # populated by caller from group ordering
        "conference_rank": None,    # populated by caller
        "playoff_seed": None,       # populated by caller
        "strength_of_schedule": _float("opponentWinPercent"),
        "home_wins": home_wins,
        "home_losses": home_losses,
        "away_wins": away_wins,
        "away_losses": away_losses,
    }
