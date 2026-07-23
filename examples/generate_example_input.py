"""Generate the example files for the scoring system.

Creates two files next to this script:

* ``example_input.xlsx`` — the **main scoring file**, keyed by BIB NUMBER
  (BIB NUMBER, GENDER, EVENT NAME, PERFORMANCE TYPE, RESULT), with multi-event
  athletes (same bib) and a few deliberately invalid rows.
* ``example_mapping.xlsx`` — the **optional mapping file**
  (BIB NUMBER, NAME, ID, COLLEGE) that enriches the output with identity.

The mapping deliberately (a) omits one competing bib to show that an unmapped
bib still scores with blank identity, and (b) leaves one COLLEGE blank to show
partially-missing columns are fine.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

# --- Main scoring file: BIB NUMBER, GENDER, EVENT NAME, TYPE, RESULT ---------
_MAIN_HEADERS = ("BIB NUMBER", "GENDER", "EVENT NAME", "PERFORMANCE TYPE", "RESULT")

_MAIN_ROWS: list[tuple] = [
    ("101", "Male",   "100m",          "TIME",     "10.87"),
    ("102", "Male",   "200m",          "TIME",     "21.44"),
    ("103", "Male",   "400m",          "TIME",     "48.90"),
    ("104", "Male",   "800m",          "TIME",     "1:52.30"),
    ("105", "Male",   "1500m",         "TIME",     "3:55.10"),
    ("106", "Male",   "110m Hurdles",  "TIME",     "14.55"),
    ("107", "Male",   "Long Jump",     "DISTANCE", "7.35"),
    ("108", "Male",   "Shot Put",      "DISTANCE", "16.20"),
    ("109", "Male",   "Javelin Throw", "DISTANCE", "68.40"),
    ("110", "Male",   "High Jump",     "DISTANCE", "2.10"),
    ("201", "Female", "100m",          "TIME",     "11.90"),
    ("202", "Female", "200m",          "TIME",     "24.30"),
    ("203", "Female", "400m",          "TIME",     "54.20"),
    ("204", "Female", "800m",          "TIME",     "2:05.31"),
    ("205", "Female", "100m Hurdles",  "TIME",     "13.85"),
    ("206", "Female", "Long Jump",     "DISTANCE", "6.35"),
    ("207", "Female", "Shot Put",      "DISTANCE", "14.10"),
    ("208", "Female", "Javelin Throw", "DISTANCE", "52.35"),
    ("209", "Female", "High Jump",     "DISTANCE", "1.82"),
    ("210", "Female", "1500m",         "TIME",     "4:15.60"),
    # --- Multi-event athletes (same bib -> scores summed) ------------------
    ("101", "Male",   "Long Jump",     "DISTANCE", "7.10"),
    ("101", "Male",   "200m",          "TIME",     "21.90"),
    ("201", "Female", "200m",          "TIME",     "24.10"),
    ("201", "Female", "Long Jump",     "DISTANCE", "5.95"),
    # --- Deliberately invalid rows (skipped and reported) ------------------
    ("901", "Male",   "Tug of War",    "DISTANCE", "5.00"),        # unknown event
    ("902", "Female", "100m",          "TIME",     "not-a-time"),  # bad result
    ("",    "Male",   "100m",          "TIME",     "10.50"),       # empty bib
]

# --- Optional mapping file: BIB NUMBER, NAME, ID, COLLEGE --------------------
_MAP_HEADERS = ("BIB NUMBER", "NAME", "ID", "COLLEGE")

_MAP_ROWS: list[tuple] = [
    ("101", "Aarav Sharma",  "M001", "Fergusson College"),
    ("102", "Rahul Verma",   "M002", "St. Xavier's"),
    ("103", "Karan Patel",   "M003", "Loyola College"),
    ("104", "Vikram Singh",  "M004", "Fergusson College"),
    ("105", "Arjun Nair",    "M005", ""),  # college intentionally blank
    ("106", "Rohan Das",     "M006", "St. Xavier's"),
    ("107", "Aditya Rao",    "M007", "Loyola College"),
    ("108", "Sameer Khan",   "M008", "Christ University"),
    ("109", "Nikhil Reddy",  "M009", "Fergusson College"),
    # 110 (Yash) intentionally omitted -> unmapped, scores with blank identity
    ("201", "Priya Menon",   "W001", "Fergusson College"),
    ("202", "Sneha Iyer",    "W002", "St. Xavier's"),
    ("203", "Ananya Bose",   "W003", "Loyola College"),
    ("204", "Divya Pillai",  "W004", "Christ University"),
    ("205", "Meera Joshi",   "W005", "Fergusson College"),
    ("206", "Kavya Nair",    "W006", "St. Xavier's"),
    ("207", "Ritika Shah",   "W007", "Loyola College"),
    ("208", "Pooja Desai",   "W008", "Christ University"),
    ("209", "Isha Kapoor",   "W009", "Fergusson College"),
    ("210", "Tanvi Rao",     "W010", "St. Xavier's"),
]


def _write(path: Path, title: str, headers: tuple, rows: list[tuple]) -> None:
    """Write a single-sheet workbook."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title
    sheet.append(list(headers))
    for row in rows:
        sheet.append(list(row))
    workbook.save(path)
    print(f"Wrote {path} ({len(rows)} rows)")


def main() -> None:
    """Write both example workbooks next to this script."""
    here = Path(__file__).resolve().parent
    _write(here / "example_input.xlsx", "Entries", _MAIN_HEADERS, _MAIN_ROWS)
    _write(here / "example_mapping.xlsx", "Athletes", _MAP_HEADERS, _MAP_ROWS)


if __name__ == "__main__":
    main()
