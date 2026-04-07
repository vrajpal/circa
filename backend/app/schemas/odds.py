from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OddsSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    game_id: int
    source: str
    spread_home: float | None
    total: float | None
    moneyline_home: int | None
    moneyline_away: int | None
    is_opening: bool
    captured_at: datetime
