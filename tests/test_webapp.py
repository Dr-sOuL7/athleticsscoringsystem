"""Integration tests for the Flask web application.

These exercise the full HTTP surface with Flask's test client, using the same
scoring engine the CLI uses.  Run with::

    python -m unittest tests.test_webapp
"""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from webapp import create_app
from webapp.config import Config
from webapp.service import ProcessingError, ScoringService

_REPO = Path(__file__).resolve().parent.parent
_EXAMPLE_CSV = _REPO / "examples" / "example_input.csv"

_GOOD_CSV = (
    "NAME,ID,COLLEGE,GENDER,EVENT NAME,PERFORMANCE TYPE,RESULT\n"
    "Aarav,M1,Red College,Male,100m,TIME,10.87\n"
    "Aarav,M1,Red College,Male,Long Jump,DISTANCE,7.10\n"
    "Priya,W1,Blue College,Female,100m,TIME,11.90\n"
).encode("utf-8")


class WebAppTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def _post_file(self, data: bytes, filename: str):
        return self.client.post(
            "/score",
            data={"file": (io.BytesIO(data), filename)},
            content_type="multipart/form-data",
            follow_redirects=True,
        )


class TestPages(WebAppTestBase):
    def test_index_ok(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"upload-form", r.data)

    def test_help_ok(self):
        self.assertEqual(self.client.get("/help").status_code, 200)

    def test_example_scores_and_offers_download(self):
        r = self.client.get("/example")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Athlete ranking", r.data)
        self.assertIn(b"/download/", r.data)


class TestScoringFlow(WebAppTestBase):
    def test_upload_good_csv_shows_rankings(self):
        r = self._post_file(_GOOD_CSV, "entries.csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Athlete ranking", r.data)
        self.assertIn(b"College ranking", r.data)
        # Aarav (two events) should be present and outrank single-event Priya.
        self.assertIn(b"Aarav", r.data)
        self.assertIn(b"Blue College", r.data)

    def test_download_returns_xlsx(self):
        import re

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
        r = self._post_file(b"hello", "notes.txt")
        self.assertIn(b"Unsupported file type", r.data)

    def test_missing_columns(self):
        r = self._post_file(b"FOO,BAR\n1,2\n", "bad.csv")
        self.assertIn(b"Missing required column", r.data)

    def test_empty_file(self):
        r = self._post_file(b"", "empty.csv")
        self.assertIn(b"empty", r.data.lower())


class TestServiceLayer(unittest.TestCase):
    """The service is Flask-free and can be tested directly."""

    @classmethod
    def setUpClass(cls):
        cls.service = ScoringService()

    def test_process_good_file(self):
        outcome = self.service.process_upload("x.csv", _GOOD_CSV)
        self.assertEqual(outcome.athlete_count, 2)
        self.assertEqual(outcome.college_count, 2)
        self.assertEqual(outcome.rejected_count, 0)
        self.assertEqual(outcome.performance_count, 3)
        self.assertEqual(outcome.workbook_bytes[:2], b"PK")

    def test_athletes_sorted_descending(self):
        outcome = self.service.process_upload("x.csv", _GOOD_CSV)
        scores = [row["SCORE"] for row in outcome.athletes]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_missing_columns_raises(self):
        with self.assertRaises(ProcessingError):
            self.service.process_upload("bad.csv", b"A,B\n1,2\n")

    def test_config_is_env_overridable(self):
        cfg = Config()
        self.assertGreater(cfg.max_upload_bytes, 0)
        self.assertIn(".xlsx", cfg.allowed_extensions)


if __name__ == "__main__":
    unittest.main()
