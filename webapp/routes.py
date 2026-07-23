"""HTTP routes for the athletics scoring web app.

The blueprint is intentionally thin: it validates the request, delegates all
real work to :class:`webapp.service.ScoringService`, stashes the generated
workbook in the download cache, and renders templates.  No scoring logic lives
here.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from werkzeug.utils import secure_filename

from webapp.service import ProcessingError, ScoringService

_LOG = logging.getLogger("athletics.web")

bp = Blueprint("routes", __name__)

# Path to the bundled example workbook shipped with the project.
_EXAMPLE_PATH = (
    Path(__file__).resolve().parent.parent / "examples" / "example_input.xlsx"
)


def _service() -> ScoringService:
    """Return the shared scoring service from the app context."""
    return current_app.extensions["ascore_service"]


def _cache():
    """Return the shared download cache from the app context."""
    return current_app.extensions["ascore_cache"]


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


def _render_outcome(outcome) -> str:
    """Cache the workbook and render the results page for *outcome*."""
    stem = Path(secure_filename(outcome.source_filename) or "results").stem
    download_name = f"{stem}_scored.xlsx"
    token = _cache().put(download_name, outcome.workbook_bytes)
    return render_template(
        "results.html",
        outcome=outcome,
        token=token,
        preview=_config().max_preview_rows,
    )


@bp.get("/")
def index() -> str:
    """Landing page with the upload form."""
    return render_template("index.html")


@bp.get("/help")
def help_page() -> str:
    """Static 'How it works' guide."""
    return render_template("help.html")


@bp.post("/score")
def score():
    """Handle an uploaded file: validate, score, render results."""
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
    try:
        outcome = _service().process_upload(filename, data)
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
    """Score the bundled example file so users can try the app instantly."""
    if not _EXAMPLE_PATH.exists():
        flash("The example file is unavailable.", "error")
        return redirect(url_for("routes.index"))
    data = _EXAMPLE_PATH.read_bytes()
    try:
        outcome = _service().process_upload(_EXAMPLE_PATH.name, data)
    except ProcessingError as exc:  # pragma: no cover - example is known-good
        flash(str(exc), "error")
        return redirect(url_for("routes.index"))
    return _render_outcome(outcome)


@bp.get("/download/<token>")
def download(token: str):
    """Serve a previously generated workbook by its one-time token."""
    item = _cache().get(token)
    if item is None:
        flash(
            "That download link has expired. Please score the file again.",
            "warning",
        )
        return redirect(url_for("routes.index"))
    filename, data = item
    return send_file(
        io.BytesIO(data),
        mimetype=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name=filename,
    )


@bp.app_errorhandler(413)
def too_large(_error):
    """Friendly message when the upload exceeds the size limit."""
    mb = _config().max_upload_bytes // (1024 * 1024)
    flash(f"That file is too large. The limit is {mb} MB.", "error")
    return redirect(url_for("routes.index")), 302
