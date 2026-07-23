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
from athletics_scoring.mapping import AthleteMapping, bib_key
from athletics_scoring.models import (
    AthleteAggregate,
    AthletePerformance,
    CollegeRanking,
    RejectedRecord,
    ScoredResult,
    ScoringReport,
)
from athletics_scoring.tables import ScoringTables
from athletics_scoring.timing import to_fat_equivalent
from athletics_scoring.validator import ValidationError, Validator


def _athlete_key(perf: AthletePerformance) -> str:
    """Return the identity key (normalised BIB NUMBER) for an athlete.

    Bibs are compared case-insensitively and whitespace-normalised so the same
    athlete's multiple event entries group together regardless of incidental
    spacing or case.
    """
    return bib_key(perf.bib_number)


def aggregate_by_athlete(report: ScoringReport) -> list[AthleteAggregate]:
    """Collapse per-performance scores into one summed row per athlete.

    Athletes are identified by their **BIB NUMBER**.  The returned list is
    sorted by descending total score, ties broken deterministically by bib for
    reproducible output.  Identity fields (name/id/college) are left blank here;
    call :func:`apply_mapping` afterwards to enrich them.

    Args:
        report: A scoring report whose ``scored`` list holds the individual
            performances to aggregate.

    Returns:
        One :class:`AthleteAggregate` per distinct bib.
    """
    grouped: dict[str, AthleteAggregate] = {}
    for result in report.scored:
        perf = result.performance
        key = _athlete_key(perf)
        aggregate = grouped.get(key)
        if aggregate is None:
            aggregate = AthleteAggregate(
                bib_number=str(perf.bib_number).strip(),
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
        key=lambda a: (-a.total_score, str(a.bib_number))
    )
    return aggregates


def apply_mapping(
    aggregates: list[AthleteAggregate], mapping: AthleteMapping | None
) -> list[AthleteAggregate]:
    """Enrich athlete aggregates with NAME/ID/COLLEGE from a mapping.

    A bib that has no mapping entry keeps blank identity fields (its score is
    still reported).  Passing ``None`` is a no-op, so the caller can always call
    this regardless of whether a mapping file was supplied.

    Args:
        aggregates: Per-athlete aggregates to enrich in place.
        mapping: The optional bib → identity mapping.

    Returns:
        The same list, enriched, for convenient chaining.
    """
    if not mapping:
        return aggregates
    for aggregate in aggregates:
        info = mapping.get(aggregate.bib_number)
        if info is not None:
            aggregate.name = info.name
            aggregate.athlete_id = info.athlete_id
            aggregate.college = info.college
    return aggregates


def rank_colleges(aggregates: list[AthleteAggregate]) -> list[CollegeRanking]:
    """Rank colleges by the summed total score of their athletes.

    Each college's score is the sum of every member athlete's total score, so
    the college table is a direct roll-up of the per-athlete Results table.
    Colleges are grouped case/whitespace-insensitively and sorted by descending
    score, ties broken by college name for reproducibility.

    Athletes with no known college (e.g. when no mapping file was supplied, or a
    bib was unmapped) are skipped, so this returns an empty list when there is
    no college information at all.

    Args:
        aggregates: Per-athlete aggregates (as produced by
            :func:`aggregate_by_athlete`, ideally after :func:`apply_mapping`).

    Returns:
        One :class:`CollegeRanking` per distinct college (possibly empty).
    """
    grouped: dict[str, CollegeRanking] = {}
    for athlete in aggregates:
        key = " ".join(athlete.college.split()).lower()
        if key == "":
            continue  # no college information for this athlete
        college = grouped.get(key)
        if college is None:
            college = CollegeRanking(
                college=athlete.college, total_score=0, athletes=[]
            )
            grouped[key] = college
        college.total_score += athlete.total_score
        college.athletes.append(athlete)

    colleges = list(grouped.values())
    for college in colleges:
        college.athletes.sort(key=lambda a: -a.total_score)

    colleges.sort(key=lambda c: (-c.total_score, c.college.lower()))
    return colleges


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
