from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.logging_config import get_logger
from app.models import Pick, ConsensusPick, User, Game, OddsSnapshot
from app.schemas.picks import ConsensusPickCreate, ConsensusPickResponse, PickResponse
from app.services.auth import get_current_user

logger = get_logger(__name__)
router = APIRouter(prefix="/api/consensus", tags=["consensus"])


@router.get("/picks", response_model=list[PickResponse])
def get_all_user_picks(
    season: int = Query(default=None),
    week: int = Query(default=None),
    contest_type: str = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all users' picks for a given week — the core consensus view."""
    q = db.query(Pick).filter(Pick.season == (season or settings.current_season))
    if week:
        q = q.filter(Pick.week == week)
    if contest_type:
        q = q.filter(Pick.contest_type == contest_type)
    return q.order_by(Pick.user_id, Pick.game_id).all()


@router.get("/locked", response_model=list[ConsensusPickResponse])
def get_consensus_picks(
    season: int = Query(default=None),
    week: int = Query(default=None),
    contest_type: str = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ConsensusPick).filter(ConsensusPick.season == (season or settings.current_season))
    if week:
        q = q.filter(ConsensusPick.week == week)
    if contest_type:
        q = q.filter(ConsensusPick.contest_type == contest_type)
    return q.order_by(ConsensusPick.decided_at).all()


@router.post("/lock", response_model=ConsensusPickResponse, status_code=201)
def lock_consensus_pick(
    req: ConsensusPickCreate,
    week: int = Query(),
    season: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lock in a consensus pick for the group."""
    s = season or settings.current_season

    # For survivor, check team hasn't been used
    if req.contest_type == "survivor":
        existing = (
            db.query(ConsensusPick)
            .filter(
                ConsensusPick.season == s,
                ConsensusPick.contest_type == "survivor",
                ConsensusPick.picked_team_id == req.picked_team_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Team already used in survivor this season")

    # For millions, validate 5-pick limit per week
    if req.contest_type == "millions":
        count = (
            db.query(ConsensusPick)
            .filter(ConsensusPick.season == s, ConsensusPick.week == week, ConsensusPick.contest_type == "millions")
            .count()
        )
        if count >= 5:
            raise HTTPException(status_code=400, detail="Already have 5 consensus picks for millions this week")

    pick = ConsensusPick(
        season=s,
        week=week,
        contest_type=req.contest_type,
        game_id=req.game_id,
        picked_team_id=req.picked_team_id,
    )
    db.add(pick)
    db.commit()
    db.refresh(pick)
    logger.info(
        "Consensus locked: team=%s contest=%s week=%d season=%d by user=%s",
        pick.picked_team.abbreviation, req.contest_type, week, s, current_user.username,
    )
    return pick


@router.delete("/lock/{pick_id}", status_code=204)
def unlock_consensus_pick(
    pick_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pick = db.query(ConsensusPick).get(pick_id)
    if not pick:
        raise HTTPException(status_code=404, detail="Consensus pick not found")
    logger.info(
        "Consensus unlocked: team=%s contest=%s week=%d by user=%s",
        pick.picked_team.abbreviation, pick.contest_type, pick.week, current_user.username,
    )
    db.delete(pick)
    db.commit()
