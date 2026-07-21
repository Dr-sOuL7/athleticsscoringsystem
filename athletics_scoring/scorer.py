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
    AthletePerformance,
    RejectedRecord,
    ScoredResult,
    ScoringReport,
)
from athletics_scoring.tables import ScoringTables
from athletics_scoring.timing import to_fat_equivalent
from athletics_scoring.validator import ValidationError, Validator


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
