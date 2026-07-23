"""Optional BIB → identity mapping.

The main scoring file is keyed by **BIB NUMBER** only.  A separate, optional
mapping file may supply human-readable identity for each bib:

====================  =========================================
Column                Notes
====================  =========================================
``BIB NUMBER``        Required; the join key.
``NAME``              Optional; may be blank / missing.
``ID``                Optional; may be blank / missing.
``COLLEGE``           Optional; may be blank / missing.
====================  =========================================

Rules
-----
* The ``BIB NUMBER`` column must be present, and no data row may have an empty
  bib.
* **Duplicate bibs are rejected** (the whole mapping file is refused with a
  clear message) so enrichment is never ambiguous.
* Bibs are matched case-insensitively and whitespace-normalised, exactly like
  the aggregation key, so a bib maps regardless of incidental spacing/case.
"""

from __future__ import annotations

from dataclasses import dataclass


class MappingError(Exception):
    """Raised when a mapping file is structurally invalid (user-facing)."""


@dataclass(frozen=True, slots=True)
class AthleteInfo:
    """Enrichment fields for one bib (any may be blank)."""

    name: str = ""
    athlete_id: str = ""
    college: str = ""


def bib_key(bib: object) -> str:
    """Return the normalised join key for a bib (trim + collapse + casefold)."""
    return " ".join(str(bib).split()).casefold()


class AthleteMapping:
    """An immutable bib → :class:`AthleteInfo` lookup."""

    def __init__(self, entries: dict[str, AthleteInfo]) -> None:
        self._entries = entries

    def __len__(self) -> int:
        return len(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)

    def get(self, bib: object) -> AthleteInfo | None:
        """Return the :class:`AthleteInfo` for *bib*, or ``None`` if unmapped."""
        return self._entries.get(bib_key(bib))


# Header aliases accepted in the mapping file (normalised, upper-case keys).
_BIB_HEADERS = {"BIB NUMBER", "BIB", "BIB NO", "BIB NO.", "BIBNUMBER"}
_NAME_HEADERS = {"NAME"}
_ID_HEADERS = {"ID"}
_COLLEGE_HEADERS = {"COLLEGE"}


def _find(headers: list[str], names: set[str]) -> int | None:
    """Return the first column index whose header is in *names*."""
    for i, header in enumerate(headers):
        if header in names:
            return i
    return None


def build_mapping(headers: list[str], rows: list[list[object]]) -> AthleteMapping:
    """Build an :class:`AthleteMapping` from parsed header/row data.

    Args:
        headers: Normalised (upper-cased) header names.
        rows: Positional row values.

    Returns:
        A validated :class:`AthleteMapping`.

    Raises:
        MappingError: If the bib column is missing, a data row has an empty bib,
            or a bib is duplicated.
    """
    bib_idx = _find(headers, _BIB_HEADERS)
    if bib_idx is None:
        raise MappingError(
            "The mapping file must contain a 'BIB NUMBER' column."
        )
    name_idx = _find(headers, _NAME_HEADERS)
    id_idx = _find(headers, _ID_HEADERS)
    college_idx = _find(headers, _COLLEGE_HEADERS)

    def cell(row: list[object], idx: int | None) -> str:
        if idx is None or idx >= len(row):
            return ""
        value = row[idx]
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    entries: dict[str, AthleteInfo] = {}
    duplicates: list[str] = []
    for offset, row in enumerate(rows):
        # Skip fully blank rows (trailing spreadsheet artefacts).
        if all(cell(row, i) == "" for i in range(len(row))):
            continue
        bib_raw = cell(row, bib_idx)
        if bib_raw == "":
            raise MappingError(
                f"Mapping row {offset + 2} has an empty BIB NUMBER."
            )
        key = bib_key(bib_raw)
        if key in entries:
            duplicates.append(bib_raw)
            continue
        entries[key] = AthleteInfo(
            name=cell(row, name_idx),
            athlete_id=cell(row, id_idx),
            college=cell(row, college_idx),
        )

    if duplicates:
        shown = ", ".join(sorted(set(duplicates))[:10])
        raise MappingError(
            "The mapping file has duplicate BIB NUMBER entries "
            f"({shown}). Please make each bib unique and re-upload."
        )

    return AthleteMapping(entries)
