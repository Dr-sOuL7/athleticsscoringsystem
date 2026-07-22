"""A tiny thread-safe, time-limited in-memory store for generated workbooks.

The results page renders immediately from in-memory data; the actual ``.xlsx``
download is fetched in a second request via a one-time token.  Rather than
writing files to disk (which would need a cleanup job) we keep the bytes in a
process-local cache that expires entries after a configurable TTL.

This is deliberately simple and single-process.  If the app is ever scaled to
multiple workers, swap this class for a shared store (e.g. Redis) — the public
interface is intentionally minimal to make that easy.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass


@dataclass
class _Entry:
    """A cached payload with its filename and expiry timestamp."""

    filename: str
    data: bytes
    expires_at: float


class ResultCache:
    """Thread-safe TTL cache mapping opaque tokens to workbook bytes."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._items: dict[str, _Entry] = {}

    def put(self, filename: str, data: bytes) -> str:
        """Store *data* and return a fresh opaque token to retrieve it."""
        token = uuid.uuid4().hex
        expires_at = time.monotonic() + self._ttl
        with self._lock:
            self._purge_expired_locked()
            self._items[token] = _Entry(filename, data, expires_at)
        return token

    def get(self, token: str) -> tuple[str, bytes] | None:
        """Return ``(filename, data)`` for *token*, or ``None`` if absent/expired."""
        now = time.monotonic()
        with self._lock:
            entry = self._items.get(token)
            if entry is None:
                return None
            if entry.expires_at < now:
                self._items.pop(token, None)
                return None
            return entry.filename, entry.data

    def _purge_expired_locked(self) -> None:
        """Drop expired entries; caller must hold the lock."""
        now = time.monotonic()
        expired = [t for t, e in self._items.items() if e.expires_at < now]
        for token in expired:
            self._items.pop(token, None)
