"""Core data models shared across the application.

These light-weight :func:`dataclasses.dataclass` objects are the common
vocabulary that the loader, validator, scorer and writer all speak.  Keeping
them free of any I/O keeps the scoring engine fully independent of the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# The canonical column order expected on input and produced on output.
INPUT_COLUMNS: tuple[str, ...] = (
    "NAME",
    "ID",
    "COLLEGE",
    "GENDER",
    "EVENT NAME",
    "PERFORMANCE TYPE",
    "RESULT",
)

OUTPUT_COLUMNS: tuple[str, ...] = INPUT_COLUMNS + ("SCORE",)


@dataclass(slots=True)
class AthletePerformance:
    """One raw row read from the input file.

    Attributes:
        name: Athlete's full name.
        athlete_id: Bib / registration identifier (kept as text to preserve
            leading zeros).
        college: Team / college name used for future team scoring.
        gender: Raw gender token exactly as supplied in the file.
        event_name: Raw event name exactly as supplied in the file.
        performance_type: Raw performance type token (``TIME``/``DISTANCE``).
        result: Raw result string exactly as supplied.
        row_number: 1-based row index in the source file (for error messages).
        timing: Optional timing method (``FAT``/``HAND``); ``None`` -> default.
    """

    name: str
    athlete_id: str
    college: str
    gender: str
    event_name: str
    performance_type: str
    result: str
    row_number: int
    timing: Optional[str] = None


@dataclass(slots=True)
class ScoredResult:
    """A performance that has been successfully scored."""

    performance: AthletePerformance
    score: int

    def as_output_row(self) -> dict[str, object]:
        """Return the row as an ordered mapping for the writer."""
        p = self.performance
        return {
            "NAME": p.name,
            "ID": p.athlete_id,
            "COLLEGE": p.college,
            "GENDER": p.gender,
            "EVENT NAME": p.event_name,
            "PERFORMANCE TYPE": p.performance_type,
            "RESULT": p.result,
            "SCORE": self.score,
        }


@dataclass(slots=True)
class RejectedRecord:
    """A row that could not be scored, together with the reason why."""

    performance: Optional[AthletePerformance]
    row_number: int
    reason: str

    def as_output_row(self) -> dict[str, object]:
        """Return a flattened mapping suitable for the rejects report."""
        p = self.performance
        return {
            "ROW": self.row_number,
            "NAME": p.name if p else "",
            "ID": p.athlete_id if p else "",
            "COLLEGE": p.college if p else "",
            "GENDER": p.gender if p else "",
            "EVENT NAME": p.event_name if p else "",
            "PERFORMANCE TYPE": p.performance_type if p else "",
            "RESULT": p.result if p else "",
            "REASON": self.reason,
        }


@dataclass(slots=True)
class ScoringReport:
    """Aggregate outcome of a scoring run, returned by the engine."""

    scored: list[ScoredResult] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of data rows processed."""
        return len(self.scored) + len(self.rejected)
