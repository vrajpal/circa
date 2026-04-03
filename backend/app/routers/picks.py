from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import Pick, Game, Team, ConsensusPick
from app.schemas.picks import PickCreate, PickResponse, SlateWarning
from app.schemas.schedule import TeamResponse
from app.services.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/api/picks", tags=["picks"])


@router.get("/", response_model=list[PickResponse])
def list_picks(
    season: int = Query(default=None),
    week: int = Query(default=None),
    contest_type: str = Query(default=None),
    user_id: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Pick)
    q = q.filter(Pick.season == (season or settings.current_season))
    if week:
        q = q.filter(Pick.week == week)
    if contest_type:
        q = q.filter(Pick.contest_type == contest_type)
    if user_id:
        q = q.filter(Pick.user_id == user_id)
    return q.order_by(Pick.created_at).all()


@router.post("/", response_model=PickResponse, status_code=201)
def create_pick(
    req: PickCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = db.query(Game).get(req.game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    # Validate picked team is in this game
    if req.picked_team_id not in (game.home_team_id, game.away_team_id):
        raise HTTPException(status_code=400, detail="Picked team is not in this game")

    if req.contest_type not in ("millions", "survivor"):
        raise HTTPException(status_code=400, detail="contest_type must be 'millions' or 'survivor'")

    # Survivor: can't reuse a team
    if req.contest_type == "survivor":
        used = (
            db.query(ConsensusPick)
            .filter(
                ConsensusPick.season == game.season,
                ConsensusPick.contest_type == "survivor",
                ConsensusPick.picked_team_id == req.picked_team_id,
            )
            .first()
        )
        if used:
            team = db.query(Team).get(req.picked_team_id)
            raise HTTPException(status_code=400, detail=f"{team.abbreviation} already used in survivor this season")

    # Remove existing pick for this user/game/contest
    db.query(Pick).filter(
        Pick.user_id == current_user.id,
        Pick.game_id == req.game_id,
        Pick.contest_type == req.contest_type,
    ).delete()

    pick = Pick(
        user_id=current_user.id,
        game_id=req.game_id,
        season=game.season,
        week=game.week,
        contest_type=req.contest_type,
        picked_team_id=req.picked_team_id,
        comment=req.comment,
    )
    db.add(pick)
    db.commit()
    db.refresh(pick)
    return pick


@router.delete("/{pick_id}", status_code=204)
def delete_pick(
    pick_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pick = db.query(Pick).get(pick_id)
    if not pick or pick.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Pick not found")
    db.delete(pick)
    db.commit()


@router.get("/survivor/used", response_model=list[TeamResponse])
def get_used_survivor_teams(
    season: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get teams already locked in for survivor this season."""
    used = (
        db.query(Team)
        .join(ConsensusPick, ConsensusPick.picked_team_id == Team.id)
        .filter(
            ConsensusPick.season == (season or settings.current_season),
            ConsensusPick.contest_type == "survivor",
        )
        .all()
    )
    return used


@router.get("/survivor/slate-warning", response_model=SlateWarning | None)
def check_slate_warning(
    picked_team_id: int = Query(),
    season: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if picking this team would reduce the pool for a special slate."""
    s = season or settings.current_season
    team = db.query(Team).get(picked_team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Find special slate games this team plays in
    special_games = (
        db.query(Game)
        .filter(
            Game.season == s,
            Game.slate != "regular",
            (Game.home_team_id == picked_team_id) | (Game.away_team_id == picked_team_id),
        )
        .all()
    )
    if not special_games:
        return None

    # Already used teams
    used_ids = {
        r[0]
        for r in db.query(ConsensusPick.picked_team_id)
        .filter(ConsensusPick.season == s, ConsensusPick.contest_type == "survivor")
        .all()
    }

    for game in special_games:
        # Get all teams playing in this slate
        slate_games = db.query(Game).filter(Game.season == s, Game.slate == game.slate).all()
        slate_team_ids = set()
        for g in slate_games:
            slate_team_ids.add(g.home_team_id)
            slate_team_ids.add(g.away_team_id)

        available = slate_team_ids - used_ids - {picked_team_id}
        available_teams = db.query(Team).filter(Team.id.in_(available)).all() if available else []

        return SlateWarning(
            message=f"Picking {team.abbreviation} will reduce your {game.slate} slate pool to {len(available)} teams",
            slate=game.slate,
            remaining_teams=available_teams,
        )

    return None
