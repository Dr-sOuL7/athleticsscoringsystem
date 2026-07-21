"""The scoring engine — completely independent of any UI or file format.

Given already-loaded :class:`~athletics_scoring.models.AthletePerformance`
rows, the engine validates each one, converts the mark to its FAT equivalent
where relevant, looks up the World Athletics score, and returns a
:class:`~athletics_scoring.models.ScoringReport` with the scored results sorted
in descending order of score (highest first).

The engine has no knowledge of Excel, CSV, argparse or logging — it can be
driven from a CLI, a web service, a GUI or a test with equal ease.
"""

from __future__ import annotations

from collections.abc import Iterable

from athletics_scoring.events import EventRegistry
from athletics_scoring.models import (
    AthleteAggregate,
    AthletePerformance,
    RejectedRecord,
    ScoredResult,
    ScoringReport,
)
from athletics_scoring.tables import ScoringTables
from athletics_scoring.timing import to_fat_equivalent
from athletics_scoring.validator import ValidationError, Validator


def _athlete_key(perf: AthletePerformance) -> tuple[str, str, str]:
    """Return the composite identity key (NAME, ID, COLLEGE) for an athlete.

    Name and college are compared case-insensitively and whitespace-normalised;
    the id is compared as a trimmed string.  This groups the same athlete's
    multiple event entries together even when spelling case differs slightly.
    """
    name = " ".join(perf.name.split()).lower()
    athlete_id = str(perf.athlete_id).strip()
    college = " ".join(perf.college.split()).lower()
    return (name, athlete_id, college)


def aggregate_by_athlete(report: ScoringReport) -> list[AthleteAggregate]:
    """Collapse per-performance scores into one summed row per athlete.

    Athletes are identified by the composite key (NAME, ID, COLLEGE).  The
    returned list is sorted by descending total score, with ties broken
    deterministically by name then id for reproducible output.

    Args:
        report: A scoring report whose ``scored`` list holds the individual
            performances to aggregate.

    Returns:
        One :class:`AthleteAggregate` per distinct athlete.
    """
    grouped: dict[tuple[str, str, str], AthleteAggregate] = {}
    for result in report.scored:
        perf = result.performance
        key = _athlete_key(perf)
        aggregate = grouped.get(key)
        if aggregate is None:
            aggregate = AthleteAggregate(
                name=perf.name,
                athlete_id=str(perf.athlete_id),
                college=perf.college,
                gender=perf.gender,
                total_score=0,
                results=[],
            )
            grouped[key] = aggregate
        aggregate.total_score += result.score
        aggregate.results.append(result)

    aggregates = list(grouped.values())
    for aggregate in aggregates:
        # Highest-scoring event first within each athlete's breakdown.
        aggregate.results.sort(key=lambda r: -r.score)

    aggregates.sort(
        key=lambda a: (-a.total_score, a.name.lower(), str(a.athlete_id))
    )
    return aggregates


class ScoringEngine:
    """Scores athlete performances using the World Athletics tables."""

    def __init__(self, tables: ScoringTables, registry: EventRegistry | None = None) -> None:
        """Create an engine bound to a set of scoring tables.

        Args:
            tables: The loaded scoring tables.
            registry: Optional event registry; one is derived from the tables
                if not supplied.
        """
        self._tables = tables
        self._registry = registry or EventRegistry(tables.valid_codes())
        self._validator = Validator(tables, self._registry)

    @property
    def registry(self) -> EventRegistry:
        """The event registry used to resolve event names."""
        return self._registry

    def score_one(self, perf: AthletePerformance) -> ScoredResult:
        """Validate and score a single performance.

        Raises:
            ValidationError: If the row is invalid (propagated from the
                validator) — callers that want to *skip* invalid rows should
                use :meth:`score_all` instead.
        """
        validated = self._validator.validate(perf)
        lookup_value = to_fat_equivalent(
            validated.value, validated.timing, validated.event_metres
        )
        score = validated.event.score(lookup_value)
        return ScoredResult(performance=perf, score=score)

    def score_all(self, performances: Iterable[AthletePerformance]) -> ScoringReport:
        """Score many performances, skipping (and recording) invalid rows.

        The scored results are returned sorted by descending score.  Ties are
        broken deterministically by name then athlete ID so runs are
        reproducible.

        Args:
            performances: Any iterable of raw performances.

        Returns:
            A :class:`ScoringReport` with ``scored`` and ``rejected`` lists.
        """
        report = ScoringReport()
        for perf in performances:
            try:
                report.scored.append(self.score_one(perf))
            except ValidationError as exc:
                report.rejected.append(
                    RejectedRecord(
                        performance=perf,
                        row_number=perf.row_number,
                        reason=str(exc),
                    )
                )

        report.scored.sort(
            key=lambda r: (
                -r.score,
                r.performance.name.lower(),
                str(r.performance.athlete_id),
            )
        )
        return report
