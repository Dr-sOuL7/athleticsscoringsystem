"""Centralised logging configuration.

A single call to :func:`configure_logging` wires up a run that logs to both the
console and a timestamped file under ``logs/``.  The engine and CLI use the
standard :mod:`logging` module, so downstream integrations (GUI, web) can plug
in their own handlers without code changes here.
"""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    log_dir: Path | str = "logs",
    level: int = logging.INFO,
    run_name: str | None = None,
) -> Path:
    """Configure root logging to console + a timestamped file.

    Args:
        log_dir: Directory in which to create the log file (auto-created).
        level: Logging level for both handlers.
        run_name: Optional stem for the log filename; a timestamp is used
            when omitted.

    Returns:
        The path of the log file that was created.
    """
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = run_name or f"scoring_{stamp}"
    log_path = directory / f"{stem}.log"

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)
    # Remove pre-existing handlers so repeated calls (e.g. in tests) don't
    # duplicate log lines.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    return log_path
