from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OddsSnapshot
from app.schemas.odds import OddsSnapshotResponse

router = APIRouter(prefix="/api/odds", tags=["odds"])


@router.get("/game/{game_id}", response_model=list[OddsSnapshotResponse])
def get_odds_for_game(
    game_id: int,
    source: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get all odds snapshots for a game, ordered by time. Shows line movement."""
    q = db.query(OddsSnapshot).filter(OddsSnapshot.game_id == game_id)
    if source:
        q = q.filter(OddsSnapshot.source == source)
    return q.order_by(OddsSnapshot.captured_at).all()


@router.get("/game/{game_id}/latest", response_model=list[OddsSnapshotResponse])
def get_latest_odds(game_id: int, db: Session = Depends(get_db)):
    """Get the most recent odds snapshot per source for a game."""
    from sqlalchemy import func

    subq = (
        db.query(OddsSnapshot.source, func.max(OddsSnapshot.captured_at).label("max_time"))
        .filter(OddsSnapshot.game_id == game_id)
        .group_by(OddsSnapshot.source)
        .subquery()
    )
    return (
        db.query(OddsSnapshot)
        .join(subq, (OddsSnapshot.source == subq.c.source) & (OddsSnapshot.captured_at == subq.c.max_time))
        .filter(OddsSnapshot.game_id == game_id)
        .all()
    )
