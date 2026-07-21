"""Timing-method handling (FAT vs. hand timing).

The World Athletics tables are defined for **FAT** (Fully Automatic Timing).
Hand-timed marks read faster than the equivalent electronic time, so WA adds a
fixed conversion before the mark is compared against the tables.

Only FAT is *used* by default in this release, but the conversion is fully
implemented behind :func:`to_fat_equivalent` and driven by an optional
``TIMING`` input column, so hand timing can be switched on later with no change
to the scoring engine.
"""

from __future__ import annotations

from enum import Enum


class TimingMethod(str, Enum):
    """Which timing device produced a track result."""

    FAT = "FAT"    # Fully Automatic Timing (electronic) — the table baseline.
    HAND = "HAND"  # Manual stopwatch.


# WA hand-timing conversion additions (seconds), applied to sprint/hurdle races.
# Races up to and including 200 m add 0.24 s; races between 200 m and 400 m add
# 0.14 s.  Longer races have no standard conversion.
_HAND_ADD_SHORT = 0.24   # distance <= 200 m
_HAND_ADD_MEDIUM = 0.14  # 200 m < distance <= 400 m

_DEFAULT_METHOD = TimingMethod.FAT


def normalise_timing(raw: str | None) -> TimingMethod:
    """Map an optional ``TIMING`` token onto :class:`TimingMethod`.

    An empty / missing value defaults to :attr:`TimingMethod.FAT`.

    Raises:
        KeyError: If a non-empty token is not recognised.
    """
    if raw is None or str(raw).strip() == "":
        return _DEFAULT_METHOD
    key = str(raw).strip().upper()
    aliases = {
        "FAT": TimingMethod.FAT,
        "AUTO": TimingMethod.FAT,
        "ELECTRONIC": TimingMethod.FAT,
        "HAND": TimingMethod.HAND,
        "MANUAL": TimingMethod.HAND,
        "HT": TimingMethod.HAND,
    }
    if key not in aliases:
        raise KeyError(raw)
    return aliases[key]


def to_fat_equivalent(seconds: float, method: TimingMethod, event_metres: float | None) -> float:
    """Convert a raw time to its FAT equivalent for table lookup.

    Args:
        seconds: The raw time in seconds.
        method: The timing method that produced it.
        event_metres: The race distance in metres, used to choose the
            conversion band.  ``None`` disables the conversion.

    Returns:
        The FAT-equivalent time in seconds (unchanged when already FAT).
    """
    if method is TimingMethod.FAT or event_metres is None:
        return seconds
    if event_metres <= 200:
        return seconds + _HAND_ADD_SHORT
    if event_metres <= 400:
        return seconds + _HAND_ADD_MEDIUM
    return seconds
