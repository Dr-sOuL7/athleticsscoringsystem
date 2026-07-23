"""Core data models shared across the application.

These light-weight :func:`dataclasses.dataclass` objects are the common
vocabulary that the loader, validator, scorer and writer all speak.  Keeping
them free of any I/O keeps the scoring engine fully independent of the UI.

Athlete identity
----------------
An athlete is identified by their **BIB NUMBER**.  The main scoring file only
needs the bib (plus the performance columns); the human-readable
``NAME``/``ID``/``COLLEGE`` are *optional enrichment* supplied by a separate
mapping file and filled in after scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# The required columns of the main scoring file.  BIB NUMBER is the identity;
# NAME/ID/COLLEGE are no longer part of the main file.
INPUT_COLUMNS: tuple[str, ...] = (
    "BIB NUMBER",
    "GENDER",
    "EVENT NAME",
    "PERFORMANCE TYPE",
    "RESULT",
)

# Per-performance (detailed) output layout — enriched identity + event/score.
OUTPUT_COLUMNS: tuple[str, ...] = (
    "BIB NUMBER",
    "NAME",
    "ID",
    "COLLEGE",
    "GENDER",
    "EVENT NAME",
    "PERFORMANCE TYPE",
    "RESULT",
    "SCORE",
)

# Aggregated, one-row-per-athlete output layout.  Athletes are identified by
# BIB NUMBER; NAME/ID/COLLEGE are enrichment; GENDER and SCORE are reported.
AGGREGATE_COLUMNS: tuple[str, ...] = (
    "BIB NUMBER",
    "NAME",
    "ID",
    "COLLEGE",
    "GENDER",
    "SCORE",
)

# College-ranking output layout (one row per college).
COLLEGE_COLUMNS: tuple[str, ...] = ("COLLEGE", "ATHLETES", "SCORE")

# Rejected-rows output layout.  Identity here is the bib (enrichment is not
# applied to rejected rows, which never reach the aggregation step).
REJECT_COLUMNS: tuple[str, ...] = (
    "ROW",
    "BIB NUMBER",
    "GENDER",
    "EVENT NAME",
    "PERFORMANCE TYPE",
    "RESULT",
    "REASON",
)


@dataclass(slots=True)
class AthletePerformance:
    """One raw row read from the main scoring file.

    Attributes:
        bib_number: The athlete's bib — their primary identity (kept as text to
            preserve leading zeros and allow alphanumeric bibs).
        gender: Raw gender token exactly as supplied in the file.
        event_name: Raw event name exactly as supplied in the file.
        performance_type: Raw performance type token (``TIME``/``DISTANCE``).
        result: Raw result string exactly as supplied.
        row_number: 1-based row index in the source file (for error messages).
        name: Optional athlete name (enrichment; blank in the main file).
        athlete_id: Optional registration id (enrichment; blank in the main file).
        college: Optional college (enrichment; blank in the main file).
        timing: Optional timing method (``FAT``/``HAND``); ``None`` -> default.
    """

    bib_number: str
    gender: str
    event_name: str
    performance_type: str
    result: str
    row_number: int
    name: str = ""
    athlete_id: str = ""
    college: str = ""
    timing: Optional[str] = None


@dataclass(slots=True)
class ScoredResult:
    """A performance that has been successfully scored."""

    performance: AthletePerformance
    score: int

    def as_output_row(self) -> dict[str, object]:
        """Return the row as an ordered mapping for the writer.

        Identity fields (NAME/ID/COLLEGE) reflect whatever is on the
        performance; they are usually filled from the aggregate instead (see
        :meth:`AthleteAggregate.detail_rows`).
        """
        p = self.performance
        return {
            "BIB NUMBER": p.bib_number,
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

    Athletes are identified by their **BIB NUMBER**.  The ``total_score`` is the
    sum of the World Athletics points earned across every valid entry for that
    bib.  ``name``/``athlete_id``/``college`` start blank and are filled from an
    optional mapping file after scoring.

    Attributes:
        bib_number: The athlete's bib (identity; from the first entry seen).
        gender: Athlete's gender (from the first entry seen).
        total_score: Sum of scores across ``results``.
        results: The individual scored performances that make up the total,
            ordered from highest to lowest event score.
        name: Enriched athlete name (blank until a mapping is applied).
        athlete_id: Enriched registration id (blank until a mapping is applied).
        college: Enriched college (blank until a mapping is applied).
    """

    bib_number: str
    gender: str
    total_score: int
    results: list[ScoredResult] = field(default_factory=list)
    name: str = ""
    athlete_id: str = ""
    college: str = ""

    @property
    def event_count(self) -> int:
        """Number of scored events contributing to the total."""
        return len(self.results)

    def as_output_row(self) -> dict[str, object]:
        """Return the aggregated row as an ordered mapping for the writer."""
        return {
            "BIB NUMBER": self.bib_number,
            "NAME": self.name,
            "ID": self.athlete_id,
            "COLLEGE": self.college,
            "GENDER": self.gender,
            "SCORE": self.total_score,
        }

    def detail_rows(self) -> list[dict[str, object]]:
        """Return one enriched per-performance row for each scored event.

        Identity (bib/name/id/college/gender) comes from this aggregate, so the
        enrichment applied to the athlete is reflected in every detail row.
        """
        rows: list[dict[str, object]] = []
        for result in self.results:
            p = result.performance
            rows.append(
                {
                    "BIB NUMBER": self.bib_number,
                    "NAME": self.name,
                    "ID": self.athlete_id,
                    "COLLEGE": self.college,
                    "GENDER": self.gender,
                    "EVENT NAME": p.event_name,
                    "PERFORMANCE TYPE": p.performance_type,
                    "RESULT": p.result,
                    "SCORE": result.score,
                }
            )
        return rows


@dataclass(slots=True)
class CollegeRanking:
    """A college's team standing, summed from its athletes' totals.

    Only produced when college information is available (i.e. a mapping file
    supplied colleges).

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
            "BIB NUMBER": p.bib_number if p else "",
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
