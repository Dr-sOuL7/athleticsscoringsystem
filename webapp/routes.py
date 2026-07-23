"""HTTP routes for the athletics scoring web app.

The blueprint is intentionally thin: it validates the request, delegates all
real work to :class:`webapp.service.ScoringService`, and renders templates.
No scoring logic lives here.

The download is **single-request and stateless**: the generated workbook is
embedded in the results page as a base64 ``data:`` link, so no server-side
state is kept between requests.  This makes the app safe to run on stateless
serverless platforms (e.g. Vercel), where a follow-up request may land on a
different instance.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from webapp.service import ProcessingError, ScoringService

_LOG = logging.getLogger("athletics.web")

bp = Blueprint("routes", __name__)

# Paths to the bundled example files shipped with the project.
_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
_EXAMPLE_PATH = _EXAMPLES_DIR / "example_input.xlsx"
_EXAMPLE_MAPPING_PATH = _EXAMPLES_DIR / "example_mapping.xlsx"


def _service() -> ScoringService:
    """Return the shared scoring service from the app context."""
    return current_app.extensions["ascore_service"]


def _config():
    """Return the active app configuration."""
    return current_app.config["ASCORE"]


@bp.app_context_processor
def _inject_globals() -> dict:
    """Expose common values (table metadata, limits) to every template."""
    cfg = _config()
    return {
        "tables_meta": _service().tables_meta,
        "max_mb": cfg.max_upload_bytes // (1024 * 1024),
    }


def _allowed(filename: str) -> bool:
    """Return ``True`` if *filename* has an accepted extension."""
    return Path(filename).suffix.lower() in _config().allowed_extensions


_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _render_outcome(outcome) -> str:
    """Render the results page with the workbook embedded for download.

    The ``.xlsx`` is base64-encoded into a ``data:`` URI so the browser can save
    it without a second request — no server-side state is retained.
    """
    stem = Path(secure_filename(outcome.source_filename) or "results").stem
    download_name = f"{stem}_scored.xlsx"
    b64 = base64.b64encode(outcome.workbook_bytes).decode("ascii")
    download_uri = f"data:{_XLSX_MIME};base64,{b64}"
    return render_template(
        "results.html",
        outcome=outcome,
        download_uri=download_uri,
        download_name=download_name,
        preview=_config().max_preview_rows,
    )


_CSV_MIME = "text/csv"


def _csv_data_uri(path: Path) -> str | None:
    """Return a base64 ``data:`` URI for a small bundled CSV, or ``None``.

    Used to offer the ready-made example files as stateless downloads (no extra
    endpoint or server-side state — safe on serverless hosts).
    """
    if not path.exists():
        return None
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{_CSV_MIME};base64,{b64}"


@bp.get("/")
def index() -> str:
    """Landing page with the upload form, sample downloads and generator."""
    return render_template(
        "index.html",
        sample_main_uri=_csv_data_uri(_EXAMPLES_DIR / "example_input.csv"),
        sample_roster_uri=_csv_data_uri(_EXAMPLES_DIR / "example_mapping.csv"),
    )


@bp.get("/help")
def help_page() -> str:
    """Static 'How it works' guide."""
    return render_template("help.html")


@bp.post("/score")
def score():
    """Handle an uploaded file (+ optional mapping): validate, score, render."""
    file = request.files.get("file")
    if file is None or file.filename == "":
        flash("Please choose a CSV or Excel file to upload.", "error")
        return redirect(url_for("routes.index"))

    if not _allowed(file.filename):
        flash(
            "Unsupported file type. Please upload a .xlsx or .csv file.",
            "error",
        )
        return redirect(url_for("routes.index"))

    data = file.read()
    filename = secure_filename(file.filename) or "upload"

    # Optional BIB -> identity mapping file.
    mapping_filename: str | None = None
    mapping_data: bytes | None = None
    mapping_file = request.files.get("mapping")
    if mapping_file is not None and mapping_file.filename:
        if not _allowed(mapping_file.filename):
            flash(
                "Unsupported mapping file type. Please upload a .xlsx or .csv "
                "file, or leave it empty.",
                "error",
            )
            return redirect(url_for("routes.index"))
        mapping_filename = secure_filename(mapping_file.filename) or "mapping"
        mapping_data = mapping_file.read()

    try:
        outcome = _service().process_upload(
            filename, data, mapping_filename, mapping_data
        )
    except ProcessingError as exc:
        _LOG.info("Rejected upload %s: %s", filename, exc)
        flash(str(exc), "error")
        return redirect(url_for("routes.index"))
    except Exception:  # pragma: no cover - unexpected engine error
        _LOG.exception("Unexpected error processing %s", filename)
        flash(
            "Something went wrong while scoring the file. "
            "Please check the format and try again.",
            "error",
        )
        return redirect(url_for("routes.index"))

    _LOG.info(
        "Scored %s: %d athletes, %d colleges, %d rejected",
        filename,
        outcome.athlete_count,
        outcome.college_count,
        outcome.rejected_count,
    )
    if outcome.rejected_count:
        flash(
            f"{outcome.rejected_count} row(s) were skipped — see the "
            "'Rejected' tab for details.",
            "warning",
        )
    return _render_outcome(outcome)


@bp.get("/example")
def example():
    """Score the bundled example (main + mapping) so users can try it instantly."""
    if not _EXAMPLE_PATH.exists():
        flash("The example file is unavailable.", "error")
        return redirect(url_for("routes.index"))
    data = _EXAMPLE_PATH.read_bytes()
    map_name = map_data = None
    if _EXAMPLE_MAPPING_PATH.exists():
        map_name = _EXAMPLE_MAPPING_PATH.name
        map_data = _EXAMPLE_MAPPING_PATH.read_bytes()
    try:
        outcome = _service().process_upload(
            _EXAMPLE_PATH.name, data, map_name, map_data
        )
    except ProcessingError as exc:  # pragma: no cover - example is known-good
        flash(str(exc), "error")
        return redirect(url_for("routes.index"))
    return _render_outcome(outcome)


@bp.app_errorhandler(413)
def too_large(_error):
    """Friendly message when the upload exceeds the size limit."""
    mb = _config().max_upload_bytes // (1024 * 1024)
    flash(f"That file is too large. The limit is {mb} MB.", "error")
    return redirect(url_for("routes.index")), 302
