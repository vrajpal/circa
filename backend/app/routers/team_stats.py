"""FastAPI router for team statistics and standings.

Endpoints:
  GET /api/team-stats/stats             — stats for one or all teams, by season+week
  GET /api/team-stats/stats/{team_abbr} — full snapshot history for a team
  GET /api/team-stats/rankings          — all teams ranked by a stat
  GET /api/team-stats/standings         — current standings (W/L/pct/rank)
  GET /api/team-stats/matchup           — side-by-side comparison for two teams
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import Team, Game
from app.models.team_stats import TeamStatSnapshot, TeamStanding
from app.schemas.team_stats import (
    TeamStatSnapshotResponse,
    TeamStandingResponse,
    MatchupComparisonResponse,
)

router = APIRouter(prefix="/api/team-stats", tags=["team-stats"])

# Stat column names we allow ranking by — prevents arbitrary column injection
RANKABLE_STAT_COLUMNS = {
    "points_per_game",
    "total_yards_per_game",
    "passing_yards_per_game",
    "rushing_yards_per_game",
    "turnovers_per_game",
    "red_zone_td_pct",
    "third_down_pct",
    "points_allowed_per_game",
    "yards_allowed_per_game",
    "sacks_per_game",
    "takeaways_per_game",
    "point_differential_per_game",
}


def _latest_snapshot(db: Session, team_id: int, season: int) -> TeamStatSnapshot | None:
    """Return the most recent snapshot for a team in a season."""
    return (
        db.query(TeamStatSnapshot)
        .filter(
            TeamStatSnapshot.team_id == team_id,
            TeamStatSnapshot.season == season,
        )
        .order_by(TeamStatSnapshot.week.desc())
        .first()
    )


def _get_team_or_404(db: Session, abbr: str) -> Team:
    team = db.query(Team).filter(Team.abbreviation == abbr.upper()).first()
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{abbr}' not found")
    return team


# ---------------------------------------------------------------------------
# Stats endpoints
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=list[TeamStatSnapshotResponse])
def get_team_stats(
    season: int = Query(default=None, description="Defaults to current season"),
    week: int = Query(default=None, description="Specific week; defaults to latest available"),
    team: str = Query(default=None, description="Team abbreviation (e.g. KC)"),
    source: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return team stat snapshots.

    - If week is omitted, returns the latest snapshot for each team in the season.
    - If team is omitted, returns stats for all 32 teams.
    """
    season = season or settings.current_season

    if week:
        q = db.query(TeamStatSnapshot).filter(
            TeamStatSnapshot.season == season,
            TeamStatSnapshot.week == week,
        )
        if team:
            team_row = _get_team_or_404(db, team)
            q = q.filter(TeamStatSnapshot.team_id == team_row.id)
        if source:
            q = q.filter(TeamStatSnapshot.source == source)
        return q.order_by(TeamStatSnapshot.team_id).all()

    # No week specified — return the latest snapshot per team
    all_teams = db.query(Team).all()
    if team:
        all_teams = [_get_team_or_404(db, team)]

    results = []
    for t in all_teams:
        q = db.query(TeamStatSnapshot).filter(
            TeamStatSnapshot.team_id == t.id,
            TeamStatSnapshot.season == season,
        )
        if source:
            q = q.filter(TeamStatSnapshot.source == source)
        latest = q.order_by(TeamStatSnapshot.week.desc()).first()
        if latest:
            results.append(latest)
    return results


@router.get("/stats/{team_abbr}/history", response_model=list[TeamStatSnapshotResponse])
def get_team_stats_history(
    team_abbr: str,
    season: int = Query(default=None),
    source: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return the full week-by-week stat progression for a team.

    Useful for charting how a team's offense or defense trended across the season.
    """
    season = season or settings.current_season
    team = _get_team_or_404(db, team_abbr)
    q = db.query(TeamStatSnapshot).filter(
        TeamStatSnapshot.team_id == team.id,
        TeamStatSnapshot.season == season,
    )
    if source:
        q = q.filter(TeamStatSnapshot.source == source)
    return q.order_by(TeamStatSnapshot.week).all()


# ---------------------------------------------------------------------------
# Rankings endpoint
# ---------------------------------------------------------------------------

@router.get("/rankings", response_model=list[TeamStatSnapshotResponse])
def get_team_rankings(
    stat: str = Query(description=f"Stat to rank by. Options: {', '.join(sorted(RANKABLE_STAT_COLUMNS))}"),
    season: int = Query(default=None),
    ascending: bool = Query(default=False, description="True = worst-to-best (e.g. fewest points allowed)"),
    db: Session = Depends(get_db),
):
    """Return all teams ranked by a specific stat (latest snapshot per team).

    For defensive rankings like 'points_allowed_per_game', pass ascending=true
    to see the best defenses (fewest points allowed) first.
    """
    if stat not in RANKABLE_STAT_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stat '{stat}'. Choose from: {', '.join(sorted(RANKABLE_STAT_COLUMNS))}",
        )

    season = season or settings.current_season

    # Get latest snapshot per team
    all_teams = db.query(Team).all()
    snapshots = []
    for t in all_teams:
        latest = (
            db.query(TeamStatSnapshot)
            .filter(
                TeamStatSnapshot.team_id == t.id,
                TeamStatSnapshot.season == season,
            )
            .order_by(TeamStatSnapshot.week.desc())
            .first()
        )
        if latest and getattr(latest, stat) is not None:
            snapshots.append(latest)

    snapshots.sort(key=lambda s: getattr(s, stat), reverse=not ascending)
    return snapshots


# ---------------------------------------------------------------------------
# Standings endpoint
# ---------------------------------------------------------------------------

@router.get("/standings", response_model=list[TeamStandingResponse])
def get_standings(
    season: int = Query(default=None),
    conference: str = Query(default=None, description="AFC or NFC"),
    source: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return current standings, optionally filtered by conference."""
    season = season or settings.current_season

    q = db.query(TeamStanding).filter(TeamStanding.season == season)
    if source:
        q = q.filter(TeamStanding.source == source)

    standings = q.all()

    if conference:
        conf_upper = conference.upper()
        standings = [
            s for s in standings
            if s.team and s.team.conference == conf_upper
        ]

    standings.sort(key=lambda s: (s.conference_rank or 999))
    return standings


# ---------------------------------------------------------------------------
# Matchup comparison endpoint
# ---------------------------------------------------------------------------

@router.get("/matchup", response_model=MatchupComparisonResponse)
def get_matchup_comparison(
    home: str = Query(description="Home team abbreviation"),
    away: str = Query(description="Away team abbreviation"),
    season: int = Query(default=None),
    week: int = Query(default=None, description="Week of the matchup; defaults to latest available stats"),
    db: Session = Depends(get_db),
):
    """Side-by-side stat and standing comparison for two teams.

    Returns the most recent stat snapshot for each team (or the snapshot for
    a specific week if 'week' is provided). Useful for pre-game ATS analysis.
    """
    season = season or settings.current_season
    home_team = _get_team_or_404(db, home)
    away_team = _get_team_or_404(db, away)

    def _get_snapshot(team: Team) -> TeamStatSnapshot | None:
        q = db.query(TeamStatSnapshot).filter(
            TeamStatSnapshot.team_id == team.id,
            TeamStatSnapshot.season == season,
        )
        if week:
            return q.filter(TeamStatSnapshot.week == week).first()
        return q.order_by(TeamStatSnapshot.week.desc()).first()

    def _get_standing(team: Team) -> TeamStanding | None:
        return (
            db.query(TeamStanding)
            .filter(
                TeamStanding.team_id == team.id,
                TeamStanding.season == season,
            )
            .first()
        )

    home_stats = _get_snapshot(home_team)
    away_stats = _get_snapshot(away_team)
    home_standing = _get_standing(home_team)
    away_standing = _get_standing(away_team)
    resolved_week = week or (home_stats.week if home_stats else 0)

    return MatchupComparisonResponse(
        season=season,
        week=resolved_week,
        home_team=home_team,
        away_team=away_team,
        home_stats=home_stats,
        away_stats=away_stats,
        home_standing=home_standing,
        away_standing=away_standing,
    )
