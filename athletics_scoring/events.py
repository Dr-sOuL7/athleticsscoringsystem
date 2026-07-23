"""Event naming, aliases and performance-type classification.

The World Athletics workbook uses terse column codes (``LJ``, ``SP``, ``JT``,
``100m``).  Real entry files, however, tend to use friendly names
(``Long Jump``, ``Shot Put``, ``Javelin Throw``).  This module bridges the two
so the rest of the system only ever deals with a single **canonical code**.

Design notes
------------
* Resolution is *case-* and *whitespace-insensitive*.
* Plain names default to **outdoor**; the indoor short-track variants must be
  requested explicitly (``"200m sh"`` / ``"Indoor 200m"``).
* Adding a new event is a one-line change to :data:`FRIENDLY_ALIASES` (or
  simply using the official code, which always resolves out of the box).
"""

from __future__ import annotations

import re
from enum import Enum


class PerformanceType(str, Enum):
    """How a result is measured and which direction is "better"."""

    TIME = "TIME"        # seconds, lower is better  (track / road / walk)
    DISTANCE = "DISTANCE"  # metres, higher is better  (jumps / throws)
    POINTS = "POINTS"    # points, higher is better  (combined events)

    @property
    def higher_is_better(self) -> bool:
        """Return ``True`` when a larger raw value earns more points."""
        return self is not PerformanceType.TIME


class Gender(str, Enum):
    """Normalised gender used to select the correct scoring table."""

    MEN = "M"
    WOMEN = "W"


# Accepted spellings for each gender, normalised to lower-case keys.
_GENDER_ALIASES: dict[str, Gender] = {
    "m": Gender.MEN,
    "male": Gender.MEN,
    "men": Gender.MEN,
    "boy": Gender.MEN,
    "boys": Gender.MEN,
    "f": Gender.WOMEN,
    "w": Gender.WOMEN,
    "female": Gender.WOMEN,
    "women": Gender.WOMEN,
    "girl": Gender.WOMEN,
    "girls": Gender.WOMEN,
}


def normalise_gender(raw: str) -> Gender:
    """Map a free-text gender token onto :class:`Gender`.

    Raises:
        KeyError: If the token is not recognised.
    """
    key = str(raw).strip().lower()
    if key not in _GENDER_ALIASES:
        raise KeyError(raw)
    return _GENDER_ALIASES[key]


def _norm(text: str) -> str:
    """Collapse whitespace and lower-case, for lenient key matching."""
    return re.sub(r"\s+", " ", str(text).strip().lower())


# ---------------------------------------------------------------------------
# Friendly-name -> official code aliases.
#
# Keys are matched after :func:`_norm` normalisation.  Official codes always
# resolve on their own, so only *extra* human spellings need to appear here.
# ---------------------------------------------------------------------------
FRIENDLY_ALIASES: dict[str, str] = {
    # --- Jumps ---------------------------------------------------------------
    "high jump": "HJ",
    "pole vault": "PV",
    "long jump": "LJ",
    "triple jump": "TJ",
    # --- Throws --------------------------------------------------------------
    "shot put": "SP",
    "shotput": "SP",
    "shot": "SP",
    "discus": "DT",
    "discus throw": "DT",
    "hammer": "HT",
    "hammer throw": "HT",
    "javelin": "JT",
    "javelin throw": "JT",
    # --- Hurdles -------------------------------------------------------------
    "100m hurdles": "100mH",
    "110m hurdles": "110mH",
    "400m hurdles": "400mH",
    "50m hurdles": "50mH",
    "55m hurdles": "55mH",
    "60m hurdles": "60mH",
    # --- Steeplechase --------------------------------------------------------
    "2000m steeplechase": "2000m SC",
    "3000m steeplechase": "3000m SC",
    "2000m sc": "2000m SC",
    "3000m sc": "3000m SC",
    # --- Distance / road -----------------------------------------------------
    "half marathon": "HM",
    "mile": "Mile",
    "2 mile": "2 Miles",
    "2 miles": "2 Miles",
    # --- Combined events -----------------------------------------------------
    "decathlon": "Dec.",
    "heptathlon (m)": "Hept. sh",
    "heptathlon": "Heptathlon",
    "pentathlon": "Pent. Sh",
}


class EventRegistry:
    """Resolves user-supplied event names to canonical table codes.

    The set of *valid* codes is supplied by the loaded scoring tables, so the
    registry never claims to know an event the tables cannot actually score.
    """

    def __init__(self, valid_codes: set[str]) -> None:
        """Build the registry from the codes present in the scoring tables.

        Args:
            valid_codes: All canonical event codes known to the tables
                (union across both genders).
        """
        self._valid_codes = set(valid_codes)
        # Case-insensitive lookup from a normalised code back to its canonical
        # spelling, e.g. ``"200m sh"`` -> ``"200m sh"``.
        self._code_by_norm = {_norm(code): code for code in valid_codes}

    @property
    def valid_codes(self) -> set[str]:
        """The immutable set of scorable event codes."""
        return set(self._valid_codes)

    def resolve(self, event_name: str) -> str:
        """Return the canonical code for *event_name*.

        Resolution order: exact code (case-insensitive) → friendly alias.

        Raises:
            KeyError: If the name cannot be mapped to a known event.
        """
        key = _norm(event_name)

        # 1) Direct (case/whitespace-insensitive) match against a real code.
        if key in self._code_by_norm:
            return self._code_by_norm[key]

        # 2) Friendly alias -> code (the code must still exist in the tables).
        if key in FRIENDLY_ALIASES:
            code = FRIENDLY_ALIASES[key]
            if code in self._valid_codes:
                return code

        raise KeyError(event_name)
