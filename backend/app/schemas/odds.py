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
    # True when the moneyline was derived from the spread, not sourced from a book.
    moneyline_derived: bool
    is_opening: bool
    # opening / live / closing
    line_type: str
    captured_at: datetime
