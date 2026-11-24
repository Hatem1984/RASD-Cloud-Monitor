"""Offline regression: missing official dates cannot be silently excluded."""
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
import rasd_official_daily as worker
from official_ministry_source import _read_original, SAMPLE
from test_gate38_official_ministry_source import FakePage, HEADLINE

DAY = date(2026, 10, 17)

class OfficialDateProof(unittest.TestCase):
    def test_missing_date_is_hold(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
                "official_ministry_source.original_publication_date", return_value=None):
            path = Path(tmp) / "original.jpg"
            result = _read_original(FakePage(), SAMPLE, [HEADLINE.split()[0]], DAY, path)
            self.assertEqual(result, {"status": "HOLD", "reason": "publisher_date_missing"})
            self.assertFalse(path.exists())

    def test_proven_offday_has_date(self):
        with tempfile.TemporaryDirectory() as tmp, patch(
                "official_ministry_source.original_publication_date", return_value=date(2026,10,16)):
            path = Path(tmp) / "original.jpg"
            result = _read_original(FakePage(), SAMPLE, [HEADLINE.split()[0]], DAY, path)
            self.assertEqual(result, {"status": "HOLD", "reason": "publisher_date_outside_target", "published_date_cairo": "2026-10-16"})
            self.assertFalse(path.exists())

    def assert_builder_hold(self, receipt, reason):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                worker, "discover_official_newslist", return_value=[SAMPLE]), patch.object(
                worker, "_read_original", return_value=receipt), patch.object(
                worker, "render_docx", side_effect=AssertionError("must not render")), patch.object(
                worker, "protected_credentials", side_effect=AssertionError("no private reads")):
            with self.assertRaisesRegex(RuntimeError, reason):
                worker.build_official_daily(Path(tmp), target_date=DAY, browser_factory=MagicMock())

    def test_missing_date_stops_bulletin(self):
        self.assert_builder_hold({"status":"HOLD","reason":"publisher_date_missing"}, "official_original_hold_publisher_date_missing")

    def test_only_proven_older_date_skipped(self):
        self.assert_builder_hold({"status":"HOLD","reason":"publisher_date_outside_target","published_date_cairo":"2026-10-16"}, "official_no_verified_new_original_today")

    def test_unproved_offday_cannot_skip(self):
        self.assert_builder_hold({"status":"HOLD","reason":"publisher_date_outside_target"}, "official_original_hold_publisher_date_missing")

    def test_future_or_equal_date_cannot_skip(self):
        for value in ("2026-10-17", "2026-10-18"):
            self.assert_builder_hold({"status":"HOLD","reason":"publisher_date_outside_target","published_date_cairo":value}, "official_original_hold_publisher_date_inconsistent")
