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

# Per-performance (detailed) output layout.
OUTPUT_COLUMNS: tuple[str, ...] = INPUT_COLUMNS + ("SCORE",)

# Aggregated, one-row-per-athlete output layout.  Athletes are identified by
# the composite key (NAME, ID, COLLEGE); GENDER and SCORE are reported columns.
AGGREGATE_COLUMNS: tuple[str, ...] = ("NAME", "ID", "COLLEGE", "GENDER", "SCORE")

# College-ranking output layout (one row per college).
COLLEGE_COLUMNS: tuple[str, ...] = ("COLLEGE", "ATHLETES", "SCORE")


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
class AthleteAggregate:
    """All performances of one athlete, collapsed to a single scored row.

    Athletes are identified by the composite primary key (NAME, ID, COLLEGE).
    The ``total_score`` is the sum of the World Athletics points earned across
    every one of the athlete's valid entries.

    Attributes:
        name: Athlete's name (from the first entry seen).
        athlete_id: Athlete's id (from the first entry seen).
        college: Athlete's college (from the first entry seen).
        gender: Athlete's gender (from the first entry seen).
        total_score: Sum of scores across ``results``.
        results: The individual scored performances that make up the total,
            ordered from highest to lowest event score.
    """

    name: str
    athlete_id: str
    college: str
    gender: str
    total_score: int
    results: list[ScoredResult] = field(default_factory=list)

    @property
    def event_count(self) -> int:
        """Number of scored events contributing to the total."""
        return len(self.results)

    def as_output_row(self) -> dict[str, object]:
        """Return the aggregated row as an ordered mapping for the writer."""
        return {
            "NAME": self.name,
            "ID": self.athlete_id,
            "COLLEGE": self.college,
            "GENDER": self.gender,
            "SCORE": self.total_score,
        }


@dataclass(slots=True)
class CollegeRanking:
    """A college's team standing, summed from its athletes' totals.

    Attributes:
        college: College / team name (from the first athlete seen).
        total_score: Sum of every member athlete's total score.
        athletes: The member athletes, ordered highest total first.
    """

    college: str
    total_score: int
    athletes: list["AthleteAggregate"] = field(default_factory=list)

    @property
    def athlete_count(self) -> int:
        """Number of scoring athletes representing the college."""
        return len(self.athletes)

    def as_output_row(self) -> dict[str, object]:
        """Return the college row as an ordered mapping for the writer."""
        return {
            "COLLEGE": self.college,
            "ATHLETES": self.athlete_count,
            "SCORE": self.total_score,
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
