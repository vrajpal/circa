"""Centralized logging configuration.

All application logs use Python's standard logging module with a consistent
JSON-friendly format. This makes logs parseable by any log aggregator
(Loki, ELK, CloudWatch, or just grep).

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

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger once at app startup."""
    root = logging.getLogger()

    # Avoid duplicate handlers if called more than once
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Call setup_logging() first at app startup."""
    return logging.getLogger(name)
