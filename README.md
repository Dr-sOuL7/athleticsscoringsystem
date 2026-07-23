# Inter-College Athletics Meet — Scoring System

A production-quality Python application that scores athletics performances using
the **official World Athletics Scoring Tables (2025 edition)**. It reads an
Excel or CSV file of athletes' results, computes each athlete's World Athletics
points, and writes a formatted Excel file with **one row per athlete**, sorted
from highest total score to lowest.

Athletes are identified by their **BIB NUMBER**. The main scoring file needs
only the bib plus the performance columns; a single athlete may appear many
times (one row per event) and the system sums their World Athletics points
across all events into a single total. Human-readable **NAME / ID / COLLEGE**
are optional and come from a separate **roster (mapping) file** matched on bib.

It ships with **two interfaces** over the same trusted scoring engine:

- a **web application** (upload a file in the browser, view rankings, download
  Excel) — see [Web application](#web-application);
- a **command-line tool** (`main.py`) for scripting and batch runs — see
  [Command-line usage](#usage).

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
├── run_web.py                      # Local web launcher (waitress / dev server)
├── api/index.py                    # Vercel serverless entrypoint (WSGI app)
├── vercel.json                     # Vercel build + routing config
├── requirements.txt
├── README.md
├── athletics_scoring/              # The scoring engine (UI-independent)
│   ├── __init__.py
│   ├── models.py                   # Dataclasses shared across modules
│   ├── performance.py              # Unit-agnostic result parser
│   ├── events.py                   # Event/gender aliases & registry
│   ├── timing.py                   # FAT / hand-timing conversion hook
│   ├── tables.py                   # Table loading + binary-search lookup
│   ├── validator.py                # Row & column validation
│   ├── scorer.py                   # The scoring engine + aggregation/ranking
│   ├── loader.py                   # .xlsx / .csv input loader
│   ├── writer.py                   # Formatted .xlsx output writer
│   ├── logging_config.py           # Centralised logging setup
│   └── build_tables.py             # Build step: workbook -> bundled JSON
├── webapp/                         # Flask web application
│   ├── __init__.py                 # Application factory (create_app)
│   ├── config.py                   # Env-driven configuration
│   ├── service.py                  # Adapter: upload -> engine -> view models
│   ├── routes.py                   # HTTP routes (stateless upload/results)
│   ├── logging_bootstrap.py        # Web server logging
│   ├── templates/                  # Jinja2 templates (base/index/results/help)
│   └── static/                     # style.css, app.js
├── data/
│   ├── source/WA_Scoring_Tables_2025.xlsx   # Original World Athletics workbook
│   └── scoring_tables.json         # Compact bundled tables (generated)
├── examples/
│   ├── generate_example_input.py
│   ├── example_input.xlsx          # Example main file, bib-keyed (Excel)
│   ├── example_input.csv           # Example main file (CSV)
│   ├── example_mapping.xlsx        # Example roster: BIB -> NAME/ID/COLLEGE
│   ├── example_mapping.csv         # Example roster (CSV)
│   └── example_output.xlsx         # Example output
└── tests/
    ├── test_scoring.py             # Engine tests
    └── test_webapp.py              # Web app tests
```

---

## Installation

Requires **Python 3.10+**.

```bash
pip install -r requirements.txt
```

Dependencies: `openpyxl` (engine), plus `Flask` and `waitress` (web app).

---

## Web application

A clean, responsive website for non-technical users: upload a CSV/XLSX, see the
athlete and college rankings in the browser, and download the formatted Excel
workbook. It reuses the exact same scoring engine as the CLI.

### Run it locally

```bash
pip install -r requirements.txt
python run_web.py
```

Then open **http://127.0.0.1:8000** in your browser. Click **“Try the example
file”** to see it work immediately, or upload your own spreadsheet.

Options:

```bash
python run_web.py --port 5000      # choose a port
python run_web.py --host 0.0.0.0   # expose on your local network
python run_web.py --debug          # Flask dev server with auto-reload
```

### What the site does

1. **Upload** a bib-keyed results file (`.xlsx`/`.csv`), and *optionally* a
   roster file to add names and colleges (two clearly-labelled upload steps).
2. **Validate** — missing columns, bad file types, oversized files, and invalid
   rosters (missing bib column, duplicate bibs) produce a clear message; invalid
   *rows* are skipped and listed, never fatal.
3. **Score** using the World Athletics tables (engine unchanged).
4. **Display** athlete ranking (by bib, enriched when a roster is supplied),
   college ranking, a per-performance breakdown and any rejected rows — sorted
   by descending score, medals for the top three.
5. **Download** the generated Excel workbook (Results, College Ranking, Details,
   Rejected sheets).

The workbook download is **stateless**: the generated `.xlsx` is embedded in the
results page as a base64 `data:` link, so there is no second request and no
server-side state between requests (which is what makes serverless hosting
reliable).

### Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `ASCORE_MAX_UPLOAD_BYTES` | `4194304` (4 MB) | Max upload size (kept under Vercel's ~4.5 MB body cap) |
| `ASCORE_MAX_PREVIEW_ROWS` | `1000` | Max rows rendered per table (full data is always in the download) |
| `ASCORE_SECRET_KEY` | `dev-secret-change-me` | Flask secret — **set this in production** |

### Deploy to Vercel

The app runs on **Vercel Hobby** as a single Python (WSGI) function — no code
changes needed beyond what ships in the repo:

- `api/index.py` exports the Flask `app`.
- `vercel.json` builds it with `@vercel/python`, bundles the templates, static
  assets, scoring-table JSON and example files, and routes all paths to the
  function.

Steps:

1. Push this repo to GitHub.
2. In Vercel, **Import Project** → select the repo → Deploy (settings are read
   from `vercel.json`; no build command required).
3. *(Optional but recommended)* set `ASCORE_SECRET_KEY` in the project's
   Environment Variables.

**Upload size:** Vercel serverless requests are capped at ~4.5 MB. The app sets
a 4 MB limit and a client-side guard so oversized files get a clear message
rather than an opaque platform error — comfortably enough for a typical meet
(thousands of athletes). For much larger files, add a Vercel Blob direct-upload
path (a future enhancement).

### Other hosts (traditional WSGI server)

The same app is a standard WSGI application (`webapp:create_app()`), served
locally by **waitress** (`python run_web.py`). For a non-serverless deployment:

```bash
# Linux (gunicorn)
gunicorn "webapp:create_app()" --bind 0.0.0.0:8000 --workers 3

# Any platform (waitress)
waitress-serve --listen=0.0.0.0:8000 --call webapp:create_app
```

Put it behind a reverse proxy (nginx/Caddy) for TLS and set `ASCORE_SECRET_KEY`.
Processing is fully in-memory and stateless (no database, no shared cache), so
it scales horizontally without extra infrastructure.

---

## Usage

Score a main file (writes `<input>_scored.xlsx` next to it by default):

```bash
python main.py examples/example_input.xlsx
```

Enrich the output with athlete names/colleges from a roster file, and choose an
explicit output path:

```bash
python main.py examples/example_input.xlsx \
    --mapping examples/example_mapping.xlsx \
    -o results.xlsx
```

Other options:

```bash
python main.py INPUT.xlsx \
    --mapping ROSTER.xlsx \               # optional BIB -> identity file
    --tables data/scoring_tables.json \   # use a specific table file
    --no-rejects \                        # omit the "Rejected" sheet
    --log-dir logs                        # where to write the run log
```

### Input format

**Main scoring file** — one row per performance, keyed by bib:

| Column            | Description                                   |
|-------------------|-----------------------------------------------|
| `BIB NUMBER`      | Athlete's bib — the identity (text; must not be empty) |
| `GENDER`          | `Male`/`Female`/`M`/`W`/`Men`/`Women`         |
| `EVENT NAME`      | Friendly name or official code                |
| `PERFORMANCE TYPE`| `TIME` or `DISTANCE`                           |
| `RESULT`          | `10.87`, `2:05.31`, `6.72`, `52.35`, …        |
| `TIMING`          | *(optional)* `FAT` (default) or `HAND`        |

`RESULT` accepts plain seconds (`10.87`), `m:s.cc` (`2:05.31`), `h:m:s`
(`1:02:05.3`) for times, and metres (`6.72`) for distances.

**Optional roster (mapping) file** — matches each bib to identity:

| Column       | Description                                          |
|--------------|------------------------------------------------------|
| `BIB NUMBER` | Required; the join key                               |
| `NAME`       | *(optional)* athlete name                            |
| `ID`         | *(optional)* registration id                         |
| `COLLEGE`    | *(optional)* college / team name                     |

Rules: `NAME`/`ID`/`COLLEGE` may be partially missing; **duplicate bibs are
rejected**; a bib present in the main file but absent from the roster keeps its
score with blank identity; a bib in the roster but not in the main file is
simply unused.

### Output

An `.xlsx` workbook with up to four sheets:

- **Results** — one row per athlete (bib), sorted by descending total `SCORE`:

  `RANK · BIB NUMBER · NAME · ID · COLLEGE · GENDER · SCORE`

  where `SCORE` is the sum of the athlete's World Athletics points across every
  event they entered. `NAME`/`ID`/`COLLEGE` are filled from the roster (blank
  without one).

- **College Ranking** — one row per college, sorted by descending team `SCORE`:

  `RANK · COLLEGE · ATHLETES · SCORE`

  where team `SCORE` is the sum of every member athlete's total score and
  `ATHLETES` is how many scoring athletes the college fielded. Only produced
  when a roster supplies colleges (omit with `--no-colleges`).

- **Details** — the per-performance breakdown behind each total, grouped under
  the athlete (highest-scoring event first):

  `RANK · BIB NUMBER · NAME · ID · COLLEGE · GENDER · EVENT NAME · PERFORMANCE TYPE · RESULT · SCORE`

  (omit with `--no-details`.)

- **Rejected** — every skipped input row and the reason it was excluded
  (only present when rows are rejected; omit with `--no-rejects`).

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

This runs the engine tests (`test_scoring.py`) and the web-app integration
tests (`test_webapp.py`) — 38 tests in total.

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

- **Team scoring / college ranking** — implemented: `rank_colleges()` sums each
  college's athlete totals into the *College Ranking* sheet.
- **Best Athlete Award** — the top row of the aggregated Results sheet; or pick
  the maximum `AthleteAggregate.total_score`.
- **Medal tally** — group scored results by event and take the top three.
- **Meet records** — compare each scored mark against a stored records table.
- **Hand timing** — already implemented in `timing.py`; enable via the `TIMING`
  column.
- **Web UI** — implemented: the `webapp/` Flask app (upload, rankings,
  download) is a thin caller over the same engine.
- **Certificates / PDF reports / API** — build on top of `ScoringReport` /
  `ScoringOutcome`; the engine needs no changes.

---

## License

Provided for the Inter-College Athletics Meet. The World Athletics Scoring
Tables are © World Athletics.
