"""Excel output writer.

Produces the final ``.xlsx`` using :mod:`openpyxl` with the required columns in
order, rows sorted by descending score, a styled header row and frozen panes.
Optionally emits a second *Rejected* sheet listing every skipped record and its
reason, so a meet official can see exactly what was excluded and why.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from athletics_scoring.models import OUTPUT_COLUMNS, ScoringReport

_HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_REJECT_FILL = PatternFill(start_color="C00000", end_color="C00000", fill_type="solid")


class ExcelWriter:
    """Writes a :class:`ScoringReport` to a formatted ``.xlsx`` workbook."""

    def write(
        self,
        report: ScoringReport,
        path: Path | str,
        include_rejects: bool = True,
    ) -> Path:
        """Write results to *path*.

        Args:
            report: The scoring report to serialise.
            path: Destination ``.xlsx`` path.
            include_rejects: When ``True`` and rejects exist, add a second
                worksheet listing them.

        Returns:
            The resolved output path.
        """
        workbook = Workbook()
        results_sheet = workbook.active
        results_sheet.title = "Results"
        self._write_results(results_sheet, report)

        if include_rejects and report.rejected:
            reject_sheet = workbook.create_sheet("Rejected")
            self._write_rejects(reject_sheet, report)

        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(out_path)
        return out_path

    # -- Sheets --------------------------------------------------------------
    def _write_results(self, sheet: Worksheet, report: ScoringReport) -> None:
        """Write the sorted results sheet with a ranking column."""
        headers = ("RANK",) + OUTPUT_COLUMNS
        sheet.append(list(headers))
        for rank, result in enumerate(report.scored, start=1):
            row = result.as_output_row()
            sheet.append([rank] + [row[col] for col in OUTPUT_COLUMNS])
        self._style_header(sheet, len(headers), _HEADER_FILL)
        self._autofit(sheet, headers)
        sheet.freeze_panes = "A2"

    def _write_rejects(self, sheet: Worksheet, report: ScoringReport) -> None:
        """Write the rejected-records sheet."""
        headers = (
            "ROW",
            "NAME",
            "ID",
            "COLLEGE",
            "GENDER",
            "EVENT NAME",
            "PERFORMANCE TYPE",
            "RESULT",
            "REASON",
        )
        sheet.append(list(headers))
        for reject in report.rejected:
            row = reject.as_output_row()
            sheet.append([row[col] for col in headers])
        self._style_header(sheet, len(headers), _REJECT_FILL)
        self._autofit(sheet, headers)
        sheet.freeze_panes = "A2"

    # -- Styling helpers -----------------------------------------------------
    def _style_header(self, sheet: Worksheet, ncols: int, fill: PatternFill) -> None:
        """Apply fill / font / alignment to the header row."""
        for col in range(1, ncols + 1):
            cell = sheet.cell(row=1, column=col)
            cell.fill = fill
            cell.font = _HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")

    def _autofit(self, sheet: Worksheet, headers: tuple[str, ...]) -> None:
        """Set a reasonable width per column based on its contents."""
        for idx, header in enumerate(headers, start=1):
            letter = get_column_letter(idx)
            max_len = len(str(header))
            for cell in sheet[letter]:
                value = cell.value
                if value is not None:
                    max_len = max(max_len, len(str(value)))
            sheet.column_dimensions[letter].width = min(max_len + 2, 40)
