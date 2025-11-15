"""
Phase 6: Configure structlog for JSON output and configurable level.
"""
from __future__ import annotations

import logging
import sys

import structlog

from config import get_settings


def configure_structlog() -> None:
    """Configure structlog: JSON renderer, log level from settings."""
    level_name = get_settings().log_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
