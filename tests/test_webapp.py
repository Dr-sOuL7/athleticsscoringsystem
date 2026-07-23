"""Integration tests for the Flask web application (BIB identity + roster).

These exercise the full HTTP surface with Flask's test client, using the same
scoring engine the CLI uses.  Run with::

    python -m unittest tests.test_webapp
"""

from __future__ import annotations

import io
import re
import unittest
from pathlib import Path

from webapp import create_app
from webapp.config import Config
from webapp.service import ProcessingError, ScoringService

_REPO = Path(__file__).resolve().parent.parent

# Main scoring file: bib 101 has two events (summed), bib 201 has one.
_MAIN_CSV = (
    "BIB NUMBER,GENDER,EVENT NAME,PERFORMANCE TYPE,RESULT\n"
    "101,Male,100m,TIME,10.87\n"
    "101,Male,Long Jump,DISTANCE,7.10\n"
    "201,Female,100m,TIME,11.90\n"
).encode("utf-8")

# Optional roster mapping bib -> identity (201 intentionally omitted).
_MAP_CSV = (
    "BIB NUMBER,NAME,ID,COLLEGE\n"
    "101,Aarav,M1,Red College\n"
).encode("utf-8")

_DUP_MAP_CSV = b"BIB NUMBER,NAME\n101,A\n101,B\n"


class WebAppTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def _post(self, main: bytes, filename: str = "main.csv",
              mapping: bytes | None = None, mapping_name: str = "map.csv"):
        data = {"file": (io.BytesIO(main), filename)}
        if mapping is not None:
            data["mapping"] = (io.BytesIO(mapping), mapping_name)
        return self.client.post(
            "/score", data=data, content_type="multipart/form-data",
            follow_redirects=True,
        )


class TestPages(WebAppTestBase):
    def test_index_ok(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"upload-form", r.data)
        # The optional roster upload is present and labelled optional.
        self.assertIn(b'name="mapping"', r.data)

    def test_help_ok(self):
        self.assertEqual(self.client.get("/help").status_code, 200)

    def test_example_is_enriched(self):
        r = self.client.get("/example")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Athlete ranking", r.data)
        self.assertIn(b"/download/", r.data)
        # The bundled example ships a roster, so the view is enriched.
        self.assertIn(b"Enriched with roster", r.data)


class TestScoringFlow(WebAppTestBase):
    def test_bib_only_upload(self):
        r = self._post(_MAIN_CSV)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Athlete ranking", r.data)
        self.assertIn(b">101<", r.data)                 # bib shown
        self.assertIn(b"No roster uploaded", r.data)     # no-roster note
        # No college ranking without a roster.
        self.assertNotIn(b'data-tab="colleges"', r.data)

    def test_bib_plus_roster_enriches(self):
        r = self._post(_MAIN_CSV, mapping=_MAP_CSV)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Enriched with roster", r.data)
        self.assertIn(b"Aarav", r.data)                  # enriched name
        self.assertIn(b"Red College", r.data)
        self.assertIn(b'data-tab="colleges"', r.data)    # college tab appears

    def test_download_returns_xlsx(self):
        r = self.client.get("/example")
        token = re.search(rb"/download/([0-9a-f]+)", r.data).group(1).decode()
        d = self.client.get(f"/download/{token}")
        self.assertEqual(d.status_code, 200)
        self.assertEqual(d.data[:2], b"PK")  # xlsx is a zip
        self.assertIn("attachment", d.headers.get("Content-Disposition", ""))

    def test_expired_or_unknown_token_redirects(self):
        r = self.client.get("/download/deadbeef", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"expired", r.data.lower())


class TestErrorHandling(WebAppTestBase):
    def test_no_file(self):
        r = self.client.post(
            "/score", data={}, content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Please choose", r.data)

    def test_bad_extension(self):
        r = self._post(b"hello", filename="notes.txt")
        self.assertIn(b"Unsupported file type", r.data)

    def test_missing_columns(self):
        r = self._post(b"FOO,BAR\n1,2\n", filename="bad.csv")
        self.assertIn(b"Missing required column", r.data)

    def test_empty_file(self):
        r = self._post(b"", filename="empty.csv")
        self.assertIn(b"empty", r.data.lower())

    def test_duplicate_bibs_in_roster_rejected(self):
        r = self._post(_MAIN_CSV, mapping=_DUP_MAP_CSV)
        self.assertIn(b"duplicate BIB NUMBER", r.data)

    def test_roster_missing_bib_column_rejected(self):
        r = self._post(_MAIN_CSV, mapping=b"NAME,ID\nX,1\n")
        self.assertIn(b"must contain a", r.data)

    def test_bad_roster_extension_rejected(self):
        r = self._post(_MAIN_CSV, mapping=b"x", mapping_name="roster.txt")
        self.assertIn(b"Unsupported mapping file type", r.data)


class TestServiceLayer(unittest.TestCase):
    """The service is Flask-free and can be tested directly."""

    @classmethod
    def setUpClass(cls):
        cls.service = ScoringService()

    def test_bib_only_no_colleges(self):
        outcome = self.service.process_upload("x.csv", _MAIN_CSV)
        self.assertEqual(outcome.athlete_count, 2)
        self.assertEqual(outcome.college_count, 0)
        self.assertFalse(outcome.mapping_used)
        self.assertEqual(outcome.performance_count, 3)
        self.assertEqual(outcome.workbook_bytes[:2], b"PK")
        # Identity blank without a roster.
        self.assertTrue(all(row["NAME"] == "" for row in outcome.athletes))

    def test_roster_enriches_and_unmapped_stays_blank(self):
        outcome = self.service.process_upload(
            "x.csv", _MAIN_CSV, "map.csv", _MAP_CSV
        )
        self.assertTrue(outcome.mapping_used)
        self.assertEqual(outcome.mapping_entries, 1)
        self.assertEqual(outcome.college_count, 1)
        by_bib = {row["BIB NUMBER"]: row for row in outcome.athletes}
        self.assertEqual(by_bib["101"]["NAME"], "Aarav")
        self.assertEqual(by_bib["101"]["COLLEGE"], "Red College")
        # 201 is unmapped -> blank identity but still scored.
        self.assertEqual(by_bib["201"]["NAME"], "")
        self.assertGreater(by_bib["201"]["SCORE"], 0)

    def test_athletes_sorted_descending(self):
        outcome = self.service.process_upload("x.csv", _MAIN_CSV)
        scores = [row["SCORE"] for row in outcome.athletes]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_bib_row_is_rejected(self):
        data = _MAIN_CSV + b",Male,100m,TIME,10.50\n"
        outcome = self.service.process_upload("x.csv", data)
        self.assertEqual(outcome.rejected_count, 1)
        self.assertIn("BIB NUMBER", outcome.rejected[0]["REASON"])

    def test_duplicate_bibs_raise(self):
        with self.assertRaises(ProcessingError):
            self.service.process_upload("x.csv", _MAIN_CSV, "m.csv", _DUP_MAP_CSV)

    def test_missing_columns_raises(self):
        with self.assertRaises(ProcessingError):
            self.service.process_upload("bad.csv", b"A,B\n1,2\n")

    def test_config_is_env_overridable(self):
        cfg = Config()
        self.assertGreater(cfg.max_upload_bytes, 0)
        self.assertIn(".xlsx", cfg.allowed_extensions)


if __name__ == "__main__":
    unittest.main()
