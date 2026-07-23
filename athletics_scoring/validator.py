"""Validation of raw input rows against the scoring tables.

The validator is the single gatekeeper between messy real-world files and the
scoring engine.  It resolves gender, event and timing tokens, checks that the
result is parseable, and confirms that the declared ``PERFORMANCE TYPE`` is
consistent with the event.  Anything it cannot vouch for is reported as a
:class:`ValidationError` with a human-readable reason, so the engine can skip
that single row and carry on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from athletics_scoring.events import (
    EventRegistry,
    Gender,
    PerformanceType,
    normalise_gender,
)
from athletics_scoring.models import INPUT_COLUMNS, AthletePerformance
from athletics_scoring.performance import PerformanceParseError, parse_performance
from athletics_scoring.tables import EventTable, ScoringTables
from athletics_scoring.timing import TimingMethod, normalise_timing

# Extracts the leading race distance in metres from a code such as ``"200m"``,
# ``"200m sh"``, ``"110mH"`` or ``"4x400m"`` (the last multiplied out).
_METRES_RE = re.compile(r"^(?:(\d+)x)?(\d+)\s*m", re.IGNORECASE)


class ValidationError(Exception):
    """Raised for a single row that cannot be scored."""


@dataclass(slots=True, frozen=True)
class ValidatedPerformance:
    """A fully-resolved, ready-to-score performance."""

    performance: AthletePerformance
    gender: Gender
    event: EventTable
    value: float
    timing: TimingMethod

    @property
    def event_metres(self) -> float | None:
        """Race distance in metres, or ``None`` for field/road/combined events."""
        if self.event.performance_type is not PerformanceType.TIME:
            return None
        match = _METRES_RE.match(self.event.code)
        if not match:
            return None
        multiplier = int(match.group(1)) if match.group(1) else 1
        return multiplier * int(match.group(2))


def check_columns(columns: list[str]) -> None:
    """Validate that all required input columns are present.

    Args:
        columns: The header names found in the input file.

    Raises:
        ValidationError: If any required column is missing (all missing columns
            are reported at once).
    """
    present = {c.strip().upper() for c in columns}
    missing = [c for c in INPUT_COLUMNS if c not in present]
    if missing:
        raise ValidationError(
            "Missing required column(s): " + ", ".join(missing) + ". "
            "Expected columns: " + ", ".join(INPUT_COLUMNS) + "."
        )


class Validator:
    """Resolves and validates individual rows against the scoring tables."""

    def __init__(self, tables: ScoringTables, registry: EventRegistry) -> None:
        self._tables = tables
        self._registry = registry

    def validate(self, perf: AthletePerformance) -> ValidatedPerformance:
        """Validate and resolve one row.

        Returns:
            A :class:`ValidatedPerformance` ready for scoring.

        Raises:
            ValidationError: With a descriptive reason if the row is invalid.
        """
        # 1) Bib number is the athlete's identity and must not be blank.
        if not str(perf.bib_number).strip():
            raise ValidationError("BIB NUMBER is empty")

        # 2) Gender.
        try:
            gender = normalise_gender(perf.gender)
        except KeyError:
            raise ValidationError(f"Unrecognised GENDER: {perf.gender!r}")

        # 3) Event name -> canonical code, and it must exist for this gender.
        try:
            code = self._registry.resolve(perf.event_name)
        except KeyError:
            raise ValidationError(f"Unknown EVENT NAME: {perf.event_name!r}")
        event = self._tables.get_event(gender, code)
        if event is None:
            raise ValidationError(
                f"Event {perf.event_name!r} ({code}) is not available for "
                f"gender {gender.value}"
            )

        # 4) Declared performance type must match the event's real type.
        declared = str(perf.performance_type).strip().upper()
        if declared and declared != event.performance_type.value:
            # POINTS events may legitimately be declared as DISTANCE by users;
            # otherwise a mismatch is a genuine data error.
            if not (
                event.performance_type is PerformanceType.POINTS
                and declared in {"DISTANCE", "POINTS"}
            ):
                raise ValidationError(
                    f"PERFORMANCE TYPE {declared!r} does not match event "
                    f"{code} (expected {event.performance_type.value})"
                )

        # 5) Timing method (optional column; defaults to FAT).
        try:
            timing = normalise_timing(perf.timing)
        except KeyError:
            raise ValidationError(f"Unrecognised TIMING: {perf.timing!r}")

        # 6) Result must be parseable.
        try:
            value = parse_performance(perf.result)
        except PerformanceParseError:
            raise ValidationError(f"Invalid RESULT: {perf.result!r}")
        if value <= 0:
            raise ValidationError(f"RESULT must be positive: {perf.result!r}")

        return ValidatedPerformance(
            performance=perf,
            gender=gender,
            event=event,
            value=value,
            timing=timing,
        )
