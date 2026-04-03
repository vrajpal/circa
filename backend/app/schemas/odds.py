from datetime import datetime
from pydantic import BaseModel


class OddsSnapshotResponse(BaseModel):
    id: int
    game_id: int
    source: str
    spread_home: float | None
    total: float | None
    moneyline_home: int | None
    moneyline_away: int | None
    is_opening: bool
    captured_at: datetime

    class Config:
        from_attributes = True
