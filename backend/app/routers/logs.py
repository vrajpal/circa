"""API endpoint for viewing application logs.

Reads from the rotating log file and supports filtering by level, module,
search text, and pagination. Protected by auth.
"""
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict

from app.logging_config import LOG_FILE
from app.services.auth import get_current_user
from app.models import User

router = APIRouter(prefix="/api/logs", tags=["logs"])

LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
    r" \| (?P<level>\w+)\s*"
    r"\| (?P<module>[^\|]+?)\s*"
    r"\| (?P<message>.*)$"
)


class LogEntry(BaseModel):
    timestamp: str
    level: str
    module: str
    message: str


class LogResponse(BaseModel):
    entries: list[LogEntry]
    total: int
    has_more: bool


def _parse_line(line: str) -> LogEntry | None:
    """Parse a single log line into a LogEntry, or None if it doesn't match."""
    m = LOG_LINE_PATTERN.match(line.strip())
    if not m:
        return None
    return LogEntry(
        timestamp=m.group("timestamp"),
        level=m.group("level").strip(),
        module=m.group("module").strip(),
        message=m.group("message").strip(),
    )


def _read_log_lines(path: Path, max_lines: int = 10000) -> list[str]:
    """Read the log file, returning lines in reverse chronological order."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    # Return newest first
    return list(reversed(lines[-max_lines:]))


@router.get("/", response_model=LogResponse)
def get_logs(
    level: str = Query(default=None, description="Filter by level: DEBUG, INFO, WARNING, ERROR"),
    module: str = Query(default=None, description="Filter by module name (substring match)"),
    search: str = Query(default=None, description="Search in message text"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Query application logs with optional filters."""
    level_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    min_level = level_order.get(level.upper(), 0) if level else 0

    raw_lines = _read_log_lines(LOG_FILE)
    entries: list[LogEntry] = []

    for line in raw_lines:
        entry = _parse_line(line)
        if not entry:
            continue

        # Level filter
        if level_order.get(entry.level, 0) < min_level:
            continue

        # Module filter
        if module and module.lower() not in entry.module.lower():
            continue

        # Search filter
        if search and search.lower() not in entry.message.lower():
            continue

        entries.append(entry)

    total = len(entries)
    page = entries[offset : offset + limit]

    return LogResponse(
        entries=page,
        total=total,
        has_more=(offset + limit) < total,
    )
