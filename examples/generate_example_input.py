"""Generate a realistic example input workbook for the scoring system.

Creates ``examples/example_input.xlsx`` with a spread of genders, track and
field events, friendly and coded event names, plus a couple of deliberately
invalid rows to demonstrate the reject-and-continue behaviour.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

# NAME, ID, COLLEGE, GENDER, EVENT NAME, PERFORMANCE TYPE, RESULT
_ROWS: list[tuple] = [
    ("Aarav Sharma",    "M001", "Fergusson College",   "Male",   "100m",           "TIME",     "10.87"),
    ("Rahul Verma",     "M002", "St. Xavier's",        "Male",   "200m",           "TIME",     "21.44"),
    ("Karan Patel",     "M003", "Loyola College",      "Male",   "400m",           "TIME",     "48.90"),
    ("Vikram Singh",    "M004", "Fergusson College",   "Male",   "800m",           "TIME",     "1:52.30"),
    ("Arjun Nair",      "M005", "Christ University",   "Male",   "1500m",          "TIME",     "3:55.10"),
    ("Rohan Das",       "M006", "St. Xavier's",        "Male",   "110m Hurdles",   "TIME",     "14.55"),
    ("Aditya Rao",      "M007", "Loyola College",      "Male",   "Long Jump",      "DISTANCE", "7.35"),
    ("Sameer Khan",     "M008", "Christ University",   "Male",   "Shot Put",       "DISTANCE", "16.20"),
    ("Nikhil Reddy",    "M009", "Fergusson College",   "Male",   "Javelin Throw",  "DISTANCE", "68.40"),
    ("Yash Gupta",      "M010", "St. Xavier's",        "Male",   "High Jump",      "DISTANCE", "2.10"),
    ("Priya Menon",     "W001", "Fergusson College",   "Female", "100m",           "TIME",     "11.90"),
    ("Sneha Iyer",      "W002", "St. Xavier's",        "Female", "200m",           "TIME",     "24.30"),
    ("Ananya Bose",     "W003", "Loyola College",      "Female", "400m",           "TIME",     "54.20"),
    ("Divya Pillai",    "W004", "Christ University",   "Female", "800m",           "TIME",     "2:05.31"),
    ("Meera Joshi",     "W005", "Fergusson College",   "Female", "100m Hurdles",   "TIME",     "13.85"),
    ("Kavya Nair",      "W006", "St. Xavier's",        "Female", "Long Jump",      "DISTANCE", "6.35"),
    ("Ritika Shah",     "W007", "Loyola College",      "Female", "Shot Put",       "DISTANCE", "14.10"),
    ("Pooja Desai",     "W008", "Christ University",   "Female", "Javelin Throw",  "DISTANCE", "52.35"),
    ("Isha Kapoor",     "W009", "Fergusson College",   "Female", "High Jump",      "DISTANCE", "1.82"),
    ("Tanvi Rao",       "W010", "St. Xavier's",        "Female", "1500m",          "TIME",     "4:15.60"),
    # --- Deliberately invalid rows (to be skipped and reported) -------------
    ("Bad Event",       "X001", "Unknown College",     "Male",   "Tug of War",     "DISTANCE", "5.00"),
    ("Bad Result",      "X002", "Unknown College",     "Female", "100m",           "TIME",     "not-a-time"),
]

_HEADERS = (
    "NAME", "ID", "COLLEGE", "GENDER", "EVENT NAME", "PERFORMANCE TYPE", "RESULT",
)


def main() -> None:
    """Write the example workbook next to this script."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Entries"
    sheet.append(list(_HEADERS))
    for row in _ROWS:
        sheet.append(list(row))
    out = Path(__file__).resolve().parent / "example_input.xlsx"
    workbook.save(out)
    print(f"Wrote {out} ({len(_ROWS)} rows)")


if __name__ == "__main__":
    main()
