"""Input loading with automatic ``.xlsx`` / ``.csv`` format detection.

The loader is deliberately thin: it reads rows into
:class:`~athletics_scoring.models.AthletePerformance` objects and performs only
*structural* checks (file exists, required columns present).  Row-level
validation is the validator's job, keeping responsibilities cleanly separated.
"""

from __future__ import annotations

import csv
from pathlib import Path

import openpyxl

from athletics_scoring.models import AthletePerformance
from athletics_scoring.validator import check_columns

# Canonical field -> the header key it is stored under after normalisation.
_FIELD_MAP: dict[str, str] = {
    "NAME": "name",
    "ID": "athlete_id",
    "COLLEGE": "college",
    "GENDER": "gender",
    "EVENT NAME": "event_name",
    "PERFORMANCE TYPE": "performance_type",
    "RESULT": "result",
    "TIMING": "timing",  # optional
}


class LoaderError(Exception):
    """Raised for structural problems with an input file."""


def _normalise_header(name: object) -> str:
    """Upper-case and collapse whitespace in a header cell."""
    return " ".join(str(name).split()).upper() if name is not None else ""


def _cell_to_str(value: object) -> str:
    """Render a cell value as a trimmed string, preserving numeric ids.

    Integers that arrive as floats (``123.0`` from Excel) are shown without the
    trailing ``.0`` so bib numbers stay clean.
    """
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


class InputLoader:
    """Reads athlete performances from ``.xlsx`` or ``.csv`` files."""

    def load(self, path: Path | str) -> list[AthletePerformance]:
        """Load performances from *path*, auto-detecting the format.

        Args:
            path: Path to a ``.xlsx`` or ``.csv`` file.

        Returns:
            A list of raw :class:`AthletePerformance` rows.

        Raises:
            LoaderError: If the file is missing or of an unsupported type.
            ValidationError: If a required column is absent.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise LoaderError(f"Input file not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix in {".xlsx", ".xlsm"}:
            headers, rows = self._read_xlsx(file_path)
        elif suffix == ".csv":
            headers, rows = self._read_csv(file_path)
        else:
            raise LoaderError(
                f"Unsupported input format {suffix!r}; expected .xlsx or .csv"
            )

        check_columns(headers)
        return self._to_performances(headers, rows)

    # -- Format readers ------------------------------------------------------
    def _read_xlsx(self, path: Path) -> tuple[list[str], list[list[object]]]:
        """Read the first worksheet of an ``.xlsx`` file."""
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.active
            iterator = sheet.iter_rows(values_only=True)
            try:
                header_row = next(iterator)
            except StopIteration:
                return [], []
            headers = [_normalise_header(c) for c in header_row]
            rows = [list(r) for r in iterator]
            return headers, rows
        finally:
            workbook.close()

    def _read_csv(self, path: Path) -> tuple[list[str], list[list[object]]]:
        """Read a ``.csv`` file with the standard dialect."""
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.reader(fh)
            try:
                header_row = next(reader)
            except StopIteration:
                return [], []
            headers = [_normalise_header(c) for c in header_row]
            rows = [list(r) for r in reader]
            return headers, rows

    # -- Row assembly --------------------------------------------------------
    def _to_performances(
        self, headers: list[str], rows: list[list[object]]
    ) -> list[AthletePerformance]:
        """Map header/positional rows onto :class:`AthletePerformance`."""
        # Column index for each canonical header (first occurrence wins).
        index: dict[str, int] = {}
        for i, header in enumerate(headers):
            if header in _FIELD_MAP and header not in index:
                index[header] = i

        performances: list[AthletePerformance] = []
        for offset, row in enumerate(rows):
            # Skip fully blank rows (common trailing artefacts of Excel).
            if all(_cell_to_str(c) == "" for c in row):
                continue

            def get(col: str) -> str:
                pos = index.get(col)
                if pos is None or pos >= len(row):
                    return ""
                return _cell_to_str(row[pos])

            timing_value = get("TIMING")
            performances.append(
                AthletePerformance(
                    name=get("NAME"),
                    athlete_id=get("ID"),
                    college=get("COLLEGE"),
                    gender=get("GENDER"),
                    event_name=get("EVENT NAME"),
                    performance_type=get("PERFORMANCE TYPE"),
                    result=get("RESULT"),
                    row_number=offset + 2,  # +1 header, +1 to 1-base
                    timing=timing_value or None,
                )
            )
        return performances
