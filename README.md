# Inter-College Athletics Meet — Scoring System

A production-quality Python application that scores athletics performances using
the **official World Athletics Scoring Tables (2025 edition)**. It reads an
Excel or CSV file of athletes' results, computes each athlete's World Athletics
points, and writes a formatted Excel file sorted from highest score to lowest.

---

## Features

- **Official 2025 scoring tables** — all 26 sheets of the World Athletics
  workbook (82 events per gender: sprints, hurdles, relays, middle/long
  distance, road running, race walking, jumps, throws and combined events).
- **Correct scoring semantics** — track events (lower time is better) and field
  events (higher distance is better) are handled separately, and a performance
  that falls *between* two table entries always receives the **lower** score, as
  the tables require.
- **Men & Women** tables selected automatically from the `GENDER` column.
- **`.xlsx` and `.csv` input** with automatic format detection.
- **Forgiving event names** — accepts both friendly names (`Long Jump`,
  `Shot Put`, `Javelin Throw`) and official codes (`LJ`, `SP`, `JT`, `100m`),
  case- and spacing-insensitive.
- **FAT timing** by default, with a ready-to-enable **hand-timing** conversion
  hook (optional `TIMING` column).
- **Robust validation** — invalid rows (unknown event, bad result, missing
  fields, gender/event mismatch) are skipped, logged, and listed on a separate
  *Rejected* sheet; valid athletes are still scored.
- **Fast** — ~100,000 rows/second; 50,000 athletes score in under half a second.
- **Full audit log** — input file, athlete count, invalid records, output file
  and execution time are written to a timestamped log.
- **Clean, extensible architecture** — the scoring engine is completely
  independent of any UI or file format.

---

## Project structure

```
athleticsscoringsystem/
├── main.py                         # CLI entry point (orchestration only)
├── requirements.txt
├── README.md
├── athletics_scoring/              # The application package
│   ├── __init__.py
│   ├── models.py                   # Dataclasses shared across modules
│   ├── performance.py              # Unit-agnostic result parser
│   ├── events.py                   # Event/gender aliases & registry
│   ├── timing.py                   # FAT / hand-timing conversion hook
│   ├── tables.py                   # Table loading + binary-search lookup
│   ├── validator.py                # Row & column validation
│   ├── scorer.py                   # The UI-independent scoring engine
│   ├── loader.py                   # .xlsx / .csv input loader
│   ├── writer.py                   # Formatted .xlsx output writer
│   ├── logging_config.py           # Centralised logging setup
│   └── build_tables.py             # Build step: workbook -> bundled JSON
├── data/
│   ├── source/WA_Scoring_Tables_2025.xlsx   # Original World Athletics workbook
│   └── scoring_tables.json         # Compact bundled tables (generated)
├── examples/
│   ├── generate_example_input.py
│   ├── example_input.xlsx          # Example input (Excel)
│   ├── example_input.csv           # Example input (CSV)
│   └── example_output.xlsx         # Example output
└── tests/
    └── test_scoring.py
```

---

## Installation

Requires **Python 3.10+**.

```bash
pip install -r requirements.txt
```

The only runtime dependency is `openpyxl`.

---

## Usage

Score an input file (writes `<input>_scored.xlsx` next to it by default):

```bash
python main.py examples/example_input.xlsx
```

Choose an explicit output path:

```bash
python main.py examples/example_input.csv -o results.xlsx
```

Other options:

```bash
python main.py INPUT.xlsx \
    --tables data/scoring_tables.json \   # use a specific table file
    --no-rejects \                        # omit the "Rejected" sheet
    --log-dir logs                        # where to write the run log
```

### Input format

| Column            | Description                                   |
|-------------------|-----------------------------------------------|
| `NAME`            | Athlete's name                                |
| `ID`              | Bib / registration id (text; keeps leading 0s)|
| `COLLEGE`         | College / team name                           |
| `GENDER`          | `Male`/`Female`/`M`/`W`/`Men`/`Women`         |
| `EVENT NAME`      | Friendly name or official code                |
| `PERFORMANCE TYPE`| `TIME` or `DISTANCE`                           |
| `RESULT`          | `10.87`, `2:05.31`, `6.72`, `52.35`, …        |
| `TIMING`          | *(optional)* `FAT` (default) or `HAND`        |

`RESULT` accepts plain seconds (`10.87`), `m:s.cc` (`2:05.31`), `h:m:s`
(`1:02:05.3`) for times, and metres (`6.72`) for distances.

### Output

An `.xlsx` workbook with a **Results** sheet containing:

`RANK · NAME · ID · COLLEGE · GENDER · EVENT NAME · PERFORMANCE TYPE · RESULT · SCORE`

sorted by descending `SCORE`. When any rows are rejected, a **Rejected** sheet
lists each one with the reason.

---

## Regenerating the scoring tables

The compact `data/scoring_tables.json` is produced once from the original
workbook. Regenerate it (e.g. after a tables update) with:

```bash
python -m athletics_scoring.build_tables
# or with explicit paths:
python -m athletics_scoring.build_tables data/source/WA_Scoring_Tables_2025.xlsx data/scoring_tables.json
```

---

## Running the tests

```bash
python -m unittest discover -s tests -v
# or, if pytest is installed:
python -m pytest -q
```

---

## Architecture notes

The scoring engine (`scorer.py`) knows nothing about Excel, CSV, argparse or
logging — it operates purely on in-memory dataclasses. This clean separation is
what makes the system easy to extend:

```
loader → validator → scorer → writer
                ↑
             tables (binary-searched)
```

Each event stores its performance thresholds sorted ascending, so a score is a
single `O(log n)` binary search — no per-athlete linear scans.

### How scoring works

1. `RESULT` is parsed to a plain number (seconds for time, metres for distance).
2. The event's direction is applied:
   - **Time**: the score is the points of the *smallest table time ≥* the mark.
   - **Distance**: the score is the points of the *largest table distance ≤* the
     mark.
   Both implement *"between two entries → lower score."*
3. Marks better than the top of a table are capped at the maximum tabulated
   score; marks worse than the bottom score `0`.

---

## Future expandability

The design leaves clear seams for planned features:

- **Team scoring / college ranking** — `COLLEGE` is carried through every model;
  aggregate `ScoredResult.score` per college.
- **Best Athlete Award** — pick the maximum score per athlete id.
- **Medal tally** — group scored results by event and take the top three.
- **Meet records** — compare each scored mark against a stored records table.
- **Hand timing** — already implemented in `timing.py`; enable via the `TIMING`
  column.
- **Certificates / PDF reports / GUI** — build on top of `ScoringReport`; the
  engine needs no changes.

---

## License

Provided for the Inter-College Athletics Meet. The World Athletics Scoring
Tables are © World Athletics.
