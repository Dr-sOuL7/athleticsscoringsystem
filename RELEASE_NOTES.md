# Release Notes

## v1.0.0 — Athletics Meet Scorer

First stable release of the Inter-College Athletics Meet scoring system — a
scoring engine, CLI, and web app built on the official **World Athletics Scoring
Tables (2025 edition)**.

### Highlights

- **Official 2025 scoring** across all 26 tables (82 events per gender): sprints,
  hurdles, relays, middle/long distance, road running, race walking, jumps,
  throws, combined events. Track vs. field direction handled correctly, with the
  official "between two entries → lower score" rule.
- **BIB NUMBER identity.** The main results file is keyed by bib
  (`BIB NUMBER, GENDER, EVENT NAME, PERFORMANCE TYPE, RESULT`); an athlete's
  events are summed into one total.
- **Optional roster enrichment.** A separate `BIB NUMBER → NAME/ID/COLLEGE` file
  adds names and college standings. Partial columns allowed; duplicate bibs are
  rejected; unmapped bibs still score with blank identity.
- **Rankings & output.** Athlete ranking, College ranking (with a roster), a
  per-performance Details breakdown, and a Rejected sheet — all in a formatted
  `.xlsx`, sorted by descending score.
- **Robust validation.** Invalid rows (empty bib, unknown event, unreadable
  result) are skipped and reported, never fatal.
- **FAT timing** by default, with a ready hand-timing conversion hook.

### Interfaces

- **Web app** (Flask): upload a results file plus an optional roster, view
  rankings in the browser, download the Excel — designed for non-technical
  users. Run with `python run_web.py`.
- **CLI**: `python main.py INPUT.xlsx --mapping ROSTER.xlsx -o results.xlsx`.

### Quality

- **53 automated tests** (engine + web).
- **CI**: GitHub Actions runs the full suite on Ubuntu, Windows and macOS across
  Python 3.10 and 3.12 — green on `main`.
- Fast: ~100k performances/second.

### Install

```bash
pip install -r requirements.txt   # openpyxl, Flask, waitress
```

Dependencies are cross-platform; no database required.
