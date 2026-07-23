"""Command-line entry point for the Inter-College Athletics scoring system.

Usage
-----
::

    python main.py INPUT.xlsx
    python main.py INPUT.csv -o results.xlsx
    python main.py INPUT.xlsx --tables data/scoring_tables.json --no-rejects

The CLI is a *thin* orchestration layer: it wires the loader, scoring engine
and writer together, and records a full audit trail (input file, athlete
count, invalid records, output file, execution time) to a log file.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from athletics_scoring.loader import InputLoader, LoaderError
from athletics_scoring.logging_config import configure_logging
from athletics_scoring.scorer import (
    ScoringEngine,
    aggregate_by_athlete,
    rank_colleges,
)
from athletics_scoring.tables import ScoringTables
from athletics_scoring.validator import ValidationError
from athletics_scoring.writer import ExcelWriter

_LOG = logging.getLogger("athletics.main")


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="athletics-scorer",
        description="Score an athletics meet using the World Athletics tables.",
    )
    parser.add_argument("input", help="Input file (.xlsx or .csv).")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output .xlsx path (default: <input>_scored.xlsx).",
    )
    parser.add_argument(
        "--tables",
        default=None,
        help="Path to scoring_tables.json (default: bundled table).",
    )
    parser.add_argument(
        "--no-colleges",
        action="store_true",
        help="Do not add a 'College Ranking' sheet.",
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="Do not add a 'Details' sheet breaking down each performance.",
    )
    parser.add_argument(
        "--no-rejects",
        action="store_true",
        help="Do not add a 'Rejected' sheet for skipped rows.",
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for log files (default: ./logs).",
    )
    return parser


def _default_output(input_path: Path) -> Path:
    """Derive a default output path from the input path."""
    return input_path.with_name(f"{input_path.stem}_scored.xlsx")


def run(argv: list[str]) -> int:
    """Execute one scoring run and return a process exit code."""
    args = _build_parser().parse_args(argv)
    log_path = configure_logging(args.log_dir)

    start = time.perf_counter()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else _default_output(input_path)

    _LOG.info("=== Athletics scoring run started ===")
    _LOG.info("Input file      : %s", input_path)
    _LOG.info("Log file        : %s", log_path)

    # 1) Load scoring tables.
    try:
        tables = ScoringTables.load(args.tables)
    except FileNotFoundError as exc:
        _LOG.error("%s", exc)
        return 2
    _LOG.info(
        "Scoring tables  : edition %s, %s men / %s women events",
        tables.meta.get("edition", "?"),
        tables.meta.get("event_count_men", "?"),
        tables.meta.get("event_count_women", "?"),
    )

    # 2) Load input.
    try:
        performances = InputLoader().load(input_path)
    except (LoaderError, ValidationError) as exc:
        _LOG.error("Failed to load input: %s", exc)
        return 2
    _LOG.info("Athletes read   : %d", len(performances))

    # 3) Score, aggregate per athlete (sum of event scores), rank colleges.
    engine = ScoringEngine(tables)
    report = engine.score_all(performances)
    aggregates = aggregate_by_athlete(report)
    colleges = rank_colleges(aggregates)
    _LOG.info("Scored records  : %d", len(report.scored))
    _LOG.info("Distinct athletes: %d", len(aggregates))
    _LOG.info("Colleges        : %d", len(colleges))
    _LOG.info("Invalid records : %d", len(report.rejected))
    for reject in report.rejected:
        _LOG.warning("  Row %s rejected: %s", reject.row_number, reject.reason)

    # 4) Write output.
    writer = ExcelWriter()
    written = writer.write(
        aggregates,
        report,
        output_path,
        colleges=None if args.no_colleges else colleges,
        include_details=not args.no_details,
        include_rejects=not args.no_rejects,
    )
    _LOG.info("Output file     : %s", written)

    elapsed = time.perf_counter() - start
    _LOG.info("Execution time  : %.3f s", elapsed)
    _LOG.info("=== Athletics scoring run finished ===")

    print(
        f"Done: {len(aggregates)} athletes ({len(report.scored)} performances), "
        f"{len(report.rejected)} rejected -> {written} ({elapsed:.3f}s)"
    )
    return 0


def main() -> None:
    """Console-script wrapper."""
    sys.exit(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
