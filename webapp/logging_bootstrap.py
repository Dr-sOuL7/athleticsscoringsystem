"""Logging setup for the web application.

Separate from the engine's per-run :mod:`athletics_scoring.logging_config`
(which creates a timestamped file per CLI run).  The web server is long-lived,
so it logs to the console and a single rotating file under ``logs/``.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE = "%Y-%m-%d %H:%M:%S"


def configure_web_logging(log_dir: Path | str = "logs", level: int = logging.INFO) -> Path:
    """Configure console + rotating-file logging for the web app.

    Args:
        log_dir: Directory for the log file (auto-created).
        level: Logging level.

    Returns:
        The path of the rotating log file.
    """
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "webapp.log"

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE)
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    return log_path
