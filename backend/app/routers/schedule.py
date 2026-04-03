from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models import Game, Team
from app.schemas.schedule import GameResponse, TeamResponse

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("/teams", response_model=list[TeamResponse])
def list_teams(db: Session = Depends(get_db)):
    return db.query(Team).order_by(Team.abbreviation).all()


@router.get("/games", response_model=list[GameResponse])
def list_games(
    season: int = Query(default=None),
    week: int = Query(default=None),
    team: str = Query(default=None, description="Team abbreviation to filter by"),
    db: Session = Depends(get_db),
):
    q = db.query(Game)
    if season:
        q = q.filter(Game.season == season)
    else:
        q = q.filter(Game.season == settings.current_season)
    if week:
        q = q.filter(Game.week == week)
    if team:
        team_row = db.query(Team).filter(Team.abbreviation == team.upper()).first()
        if team_row:
            q = q.filter((Game.home_team_id == team_row.id) | (Game.away_team_id == team_row.id))
    return q.order_by(Game.game_time).all()


@router.get("/games/{game_id}", response_model=GameResponse)
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).get(game_id)
    if not game:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Game not found")
    return game
