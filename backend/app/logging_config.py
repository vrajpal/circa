"""Centralized logging configuration.

All application logs use Python's standard logging module with a consistent
format. Logs are written to both stdout and a rotating file, making them
viewable in the terminal and queryable via the log viewer API.

Usage:
    from app.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("something happened", extra={"game_id": 42})

Log levels:
    DEBUG   — detailed diagnostic info (cache hits, query params)
    INFO    — normal operations (fetched data, added rows, request served)
    WARNING — recoverable issues (missing data, fallback used)
    ERROR   — failures that need attention (API errors, parse failures)
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log file location — next to the database in the backend directory
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "circa.log"

# Rotate at 5MB, keep 5 backups (25MB total max)
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once at app startup."""
    root = logging.getLogger()

    # Avoid duplicate handlers if called more than once
    if root.handlers:
        return

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # Rotating file handler
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Call setup_logging() first at app startup."""
    return logging.getLogger(name)
