"""
logging_tool.py
Provides a pre-configured logger used by every module in the project.
Call `get_logger(__name__)` at the top of each file.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from config.agent_config import LOG_LEVEL, LOG_FILE


_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _setup_root_logger() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Console handler — coloured on supported terminals
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
    root.addHandler(ch)

    # File handler
    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
        root.addHandler(fh)
    except OSError:
        pass  # If we can't write a log file, that's fine

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, ensuring the root logger is configured first."""
    _setup_root_logger()
    return logging.getLogger(name)
