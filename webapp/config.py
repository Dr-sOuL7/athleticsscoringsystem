"""Configuration for the athletics scoring web application.

Values can be overridden via environment variables so the same code runs
unchanged in local, staging and production settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    """Read an integer environment variable, falling back to *default*."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    """Immutable application configuration.

    Attributes:
        max_upload_bytes: Hard limit on the uploaded file size.  The default is
            4 MB so a friendly 413 is returned *before* Vercel's opaque 4.5 MB
            serverless body cap is hit.  Override for other hosts via
            ``ASCORE_MAX_UPLOAD_BYTES``.
        allowed_extensions: File extensions the uploader accepts.
        secret_key: Flask session/signing key (override in production).
        max_preview_rows: Cap on how many rows each result table renders in the
            browser (the full data is always in the downloadable workbook).
    """

    max_upload_bytes: int = _int_env("ASCORE_MAX_UPLOAD_BYTES", 4 * 1024 * 1024)
    allowed_extensions: frozenset[str] = frozenset({".csv", ".xlsx", ".xlsm"})
    secret_key: str = os.environ.get("ASCORE_SECRET_KEY", "dev-secret-change-me")
    max_preview_rows: int = _int_env("ASCORE_MAX_PREVIEW_ROWS", 1000)


# A module-level default instance is convenient for the app factory.
config = Config()
