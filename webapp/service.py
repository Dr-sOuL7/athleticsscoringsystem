"""Application service layer — the bridge between HTTP and the scoring engine.

This module is the *only* new code that touches the engine, and it does so
purely as a caller: it saves the uploaded bytes to a temporary file, runs the
**existing** loader → engine → writer pipeline, and returns plain view-model
dictionaries plus the generated workbook bytes.  The scoring logic itself is
untouched and remains fully trusted.

Keeping this layer free of Flask imports means it can be unit-tested on its own
and reused from any future interface (API, GUI, batch job).
"""

from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from athletics_scoring.loader import InputLoader, LoaderError
from athletics_scoring.mapping import AthleteMapping, MappingError
from athletics_scoring.models import (
    AthleteAggregate,
    CollegeRanking,
    ScoringReport,
)
from athletics_scoring.scorer import (
    ScoringEngine,
    aggregate_by_athlete,
    apply_mapping,
    rank_colleges,
)
from athletics_scoring.tables import ScoringTables
from athletics_scoring.validator import ValidationError


class ProcessingError(Exception):
    """Raised for a user-facing failure while processing an upload.

    The message is safe to show directly to a non-technical user.
    """


@dataclass(frozen=True)
class ScoringOutcome:
    """Everything the web layer needs to render results and offer a download.

    Attributes:
        athletes: Per-athlete rows (aggregated, sorted by descending score).
        colleges: College ranking rows (sorted by descending team score).
        rejected: Rejected input rows with reasons.
        details: Per-performance breakdown rows (athlete + event + score).
        workbook_bytes: The generated ``.xlsx`` file as bytes, ready to serve.
        source_filename: The original uploaded filename (sanitised elsewhere).
        performance_count: Number of scored individual performances.
        elapsed_seconds: Wall-clock processing time.
    """

    athletes: list[dict[str, object]]
    colleges: list[dict[str, object]]
    rejected: list[dict[str, object]]
    details: list[dict[str, object]]
    workbook_bytes: bytes
    source_filename: str
    performance_count: int
    elapsed_seconds: float
    mapping_filename: str | None = None
    mapping_entries: int = 0

    @property
    def mapping_used(self) -> bool:
        """Whether an identity mapping file was applied."""
        return self.mapping_filename is not None

    @property
    def athlete_count(self) -> int:
        """Number of distinct scored athletes."""
        return len(self.athletes)

    @property
    def college_count(self) -> int:
        """Number of distinct colleges."""
        return len(self.colleges)

    @property
    def rejected_count(self) -> int:
        """Number of rejected rows."""
        return len(self.rejected)


class ScoringService:
    """Runs uploads through the existing scoring engine.

    The scoring tables are loaded once and the resulting engine is shared across
    requests: scoring never mutates engine state (each call returns a fresh
    report), so this is safe and keeps per-request latency low.
    """

    def __init__(self, tables: ScoringTables | None = None) -> None:
        self._tables = tables or ScoringTables.load()
        self._engine = ScoringEngine(self._tables)
        self._loader = InputLoader()

    @property
    def tables_meta(self) -> dict:
        """Metadata about the loaded scoring tables (edition, event counts)."""
        return self._tables.meta

    def process_upload(
        self,
        filename: str,
        data: bytes,
        mapping_filename: str | None = None,
        mapping_data: bytes | None = None,
    ) -> ScoringOutcome:
        """Score an uploaded file and build the downloadable workbook.

        Args:
            filename: Original main-file name (used to detect the extension and
                name the output; must already be sanitised by the caller).
            data: Raw bytes of the main scoring file.
            mapping_filename: Optional mapping filename (extension detection).
            mapping_data: Optional raw bytes of the BIB->identity mapping file.

        Returns:
            A :class:`ScoringOutcome` with view-model rows and workbook bytes.

        Raises:
            ProcessingError: For any user-facing failure (bad format, missing
                columns, empty file, invalid/duplicate mapping, …) with a
                friendly message.
        """
        suffix = Path(filename).suffix.lower()
        if not data:
            raise ProcessingError("The uploaded file is empty.")

        start = time.perf_counter()
        # Work entirely inside a self-cleaning temporary directory.
        with tempfile.TemporaryDirectory(prefix="ascore_") as tmp:
            tmp_dir = Path(tmp)
            in_path = tmp_dir / f"input{suffix}"
            in_path.write_bytes(data)

            # --- Reuse the existing pipeline, unchanged --------------------
            try:
                performances = self._loader.load(in_path)
            except ValidationError as exc:
                # Structural problem such as missing required columns.
                raise ProcessingError(str(exc)) from exc
            except LoaderError as exc:
                raise ProcessingError(str(exc)) from exc

            # Optional identity mapping.
            mapping = self._load_mapping(tmp_dir, mapping_filename, mapping_data)

            report = self._engine.score_all(performances)
            aggregates = apply_mapping(aggregate_by_athlete(report), mapping)
            colleges = rank_colleges(aggregates)

            if not aggregates and report.rejected:
                # Nothing scored, but we did read rows — surface why.
                first_reason = report.rejected[0].reason
                raise ProcessingError(
                    "No rows could be scored. "
                    f"Example problem: {first_reason}"
                )
            if not aggregates and not report.rejected:
                raise ProcessingError(
                    "The file contained no data rows to score."
                )

            out_path = tmp_dir / "results.xlsx"
            from athletics_scoring.writer import ExcelWriter  # local import

            ExcelWriter().write(aggregates, report, out_path, colleges=colleges)
            workbook_bytes = out_path.read_bytes()

        elapsed = time.perf_counter() - start
        return ScoringOutcome(
            athletes=self._athlete_rows(aggregates),
            colleges=self._college_rows(colleges),
            rejected=[r.as_output_row() for r in report.rejected],
            details=self._detail_rows(aggregates),
            workbook_bytes=workbook_bytes,
            source_filename=filename,
            performance_count=len(report.scored),
            elapsed_seconds=elapsed,
            mapping_filename=mapping_filename if mapping is not None else None,
            mapping_entries=len(mapping) if mapping is not None else 0,
        )

    def _load_mapping(
        self,
        tmp_dir: Path,
        mapping_filename: str | None,
        mapping_data: bytes | None,
    ) -> AthleteMapping | None:
        """Load and validate the optional mapping file, if provided."""
        if not mapping_filename or not mapping_data:
            return None
        suffix = Path(mapping_filename).suffix.lower()
        map_path = tmp_dir / f"mapping{suffix}"
        map_path.write_bytes(mapping_data)
        try:
            return self._loader.load_mapping(map_path)
        except MappingError as exc:
            raise ProcessingError(str(exc)) from exc
        except LoaderError as exc:
            raise ProcessingError(str(exc)) from exc

    # -- View-model builders -------------------------------------------------
    @staticmethod
    def _athlete_rows(aggregates: list[AthleteAggregate]) -> list[dict]:
        """Add a 1-based rank to each aggregated athlete row."""
        rows: list[dict] = []
        for rank, agg in enumerate(aggregates, start=1):
            row = agg.as_output_row()
            row["RANK"] = rank
            row["EVENTS"] = agg.event_count
            rows.append(row)
        return rows

    @staticmethod
    def _college_rows(colleges: list[CollegeRanking]) -> list[dict]:
        """Add a 1-based rank to each college row."""
        rows: list[dict] = []
        for rank, college in enumerate(colleges, start=1):
            row = college.as_output_row()
            row["RANK"] = rank
            rows.append(row)
        return rows

    @staticmethod
    def _detail_rows(aggregates: list[AthleteAggregate]) -> list[dict]:
        """Flatten every scored performance (enriched), grouped by athlete."""
        rows: list[dict] = []
        for agg in aggregates:
            rows.extend(agg.detail_rows())
        return rows
