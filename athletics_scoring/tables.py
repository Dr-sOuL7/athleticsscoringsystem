"""Loading and querying of the World Athletics scoring tables.

The heavy lifting (parsing the 26-sheet workbook) happens once in
:mod:`athletics_scoring.build_tables`.  At runtime we only load the compact
``scoring_tables.json`` and answer point queries with an :math:`O(\\log n)`
binary search — fast enough to score tens of thousands of athletes in well
under a second.

Lookup semantics
----------------
Each event stores a ``perf`` array sorted **ascending** and a parallel ``pts``
array.  Two directions are handled:

* **Higher-is-better** (distance / points): the score is the points of the
  greatest table performance that is ``<=`` the athlete's result.
* **Lower-is-better** (time): the score is the points of the smallest table
  performance that is ``>=`` the athlete's result.

Both directions implement the official rule *"if a performance falls between
two entries, use the lower score"*.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass
from pathlib import Path

from athletics_scoring.events import Gender, PerformanceType

# Default location of the bundled JSON produced by the build step.
DEFAULT_TABLE_PATH = Path(__file__).resolve().parent.parent / "data" / "scoring_tables.json"


@dataclass(slots=True, frozen=True)
class EventTable:
    """A single event's scoring curve for one gender.

    Attributes:
        code: Canonical event code (e.g. ``"100m"``, ``"LJ"``).
        performance_type: TIME / DISTANCE / POINTS.
        perf: Performance thresholds, sorted ascending (seconds or metres).
        pts: Parallel array of point values for each threshold.
    """

    code: str
    performance_type: PerformanceType
    perf: tuple[float, ...]
    pts: tuple[int, ...]

    def score(self, value: float) -> int:
        """Return the WA points earned by *value* for this event.

        A value better than the top of the table is capped at the highest
        tabulated score; a value worse than the bottom of the table scores 0.

        Args:
            value: The parsed performance (seconds for TIME, metres for
                DISTANCE, points for POINTS).

        Returns:
            The integer World Athletics score (``0`` if below the table).
        """
        if self.performance_type.higher_is_better:
            # Greatest threshold <= value.
            idx = bisect.bisect_right(self.perf, value) - 1
            if idx < 0:
                return 0
            return self.pts[idx]

        # Lower-is-better (TIME): smallest threshold >= value.
        idx = bisect.bisect_left(self.perf, value)
        if idx == len(self.perf):
            return 0
        return self.pts[idx]


class ScoringTables:
    """In-memory access layer over the bundled scoring-table JSON."""

    def __init__(self, data: dict) -> None:
        """Build the lookup structures from a decoded JSON payload."""
        self._meta: dict = data.get("meta", {})
        self._tables: dict[Gender, dict[str, EventTable]] = {
            Gender.MEN: {},
            Gender.WOMEN: {},
        }
        gender_map = {"M": Gender.MEN, "W": Gender.WOMEN}
        for gender_key, code_map in data["events"].items():
            gender = gender_map[gender_key]
            for code, record in code_map.items():
                self._tables[gender][code] = EventTable(
                    code=code,
                    performance_type=PerformanceType(record["type"]),
                    perf=tuple(record["perf"]),
                    pts=tuple(record["pts"]),
                )

    # -- Construction --------------------------------------------------------
    @classmethod
    def load(cls, path: Path | str | None = None) -> "ScoringTables":
        """Load tables from *path* (defaults to the bundled JSON).

        Raises:
            FileNotFoundError: If the JSON file is missing.  The message points
                the user at the build step.
        """
        table_path = Path(path) if path is not None else DEFAULT_TABLE_PATH
        if not table_path.exists():
            raise FileNotFoundError(
                f"Scoring table JSON not found at {table_path}. "
                "Generate it with: python -m athletics_scoring.build_tables"
            )
        with table_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(data)

    # -- Queries -------------------------------------------------------------
    @property
    def meta(self) -> dict:
        """Metadata recorded by the build step (edition, source, counts)."""
        return dict(self._meta)

    def valid_codes(self) -> set[str]:
        """Union of event codes available for either gender."""
        codes: set[str] = set()
        for code_map in self._tables.values():
            codes.update(code_map.keys())
        return codes

    def get_event(self, gender: Gender, code: str) -> EventTable | None:
        """Return the :class:`EventTable` for *gender*/*code*, or ``None``."""
        return self._tables[gender].get(code)

    def has_event(self, gender: Gender, code: str) -> bool:
        """Return ``True`` if *code* is scorable for *gender*."""
        return code in self._tables[gender]
