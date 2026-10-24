"""Offline test of scheduled source-access HOLD versus integrity corruption."""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import scheduled_rasd as worker


class SourceHoldStatus(unittest.TestCase):
    def setUp(self):
        # Only this offline fixture emulates a genuinely scheduled worker.
        # Production event authentication remains strictly fail-closed.
        self._scheduled_env = patch.dict(os.environ, {"GITHUB_EVENT_NAME": "schedule"})
        self._scheduled_env.start()
        self.addCleanup(self._scheduled_env.stop)

    def run_case(self, reason):
        ledger = MagicMock()
        ledger.read.return_value = ({"entries": {}}, "sha")
        rows = [{"id": "a"*24}]
        def find(config, clock, *, allow_degraded, source_records):
            source_records.extend({"feed_id": f["id"], "status": "ok"}
                                  for f in config["feeds"])
            return rows
        with (patch.object(worker, "require_github_scheduler"),
              patch.object(worker, "scheduled_phase", return_value="interval"),
              patch.object(worker, "protected_credentials",
                           return_value=("s","r","p",ledger)),
              patch.object(worker, "discover_interval_news", side_effect=find),
              patch.object(worker, "prepare_source_limited_verified_word",
                           side_effect=RuntimeError(reason)),
              patch.object(worker, "reserve_stories") as reserve,
              patch.object(worker, "send_one_word") as smtp):
            try:
                result = worker.run_scheduled(
                    "interval", datetime(2026, 10, 23, 12, 30, tzinfo=timezone.utc))
                error = None
            except RuntimeError as exc:
                result, error = None, exc
        reserve.assert_not_called()
        smtp.assert_not_called()
        ledger.write.assert_not_called()
        return result, error

    def test_original_publisher_refusal_is_explicit_and_never_delivered(self):
        result, error = self.run_case("no_original_publisher_page_verified")
        self.assertIsNone(error)
        self.assertEqual(result["status"],
                         "hold_all_original_publisher_captures_unavailable")
        self.assertEqual(result["items"], 0)
        self.assertEqual(result["eligible_articles"], 1)
        self.assertEqual(result["held_articles"], 1)
        self.assertIs(result["smtp_accepted"], False)

    def test_digest_corruption_is_still_hard_error(self):
        result, error = self.run_case("original_capture_digest_mismatch")
        self.assertIsNone(result)
        self.assertEqual(str(error), "original_capture_digest_mismatch")

    def test_docx_tampering_is_still_hard_error(self):
        result, error = self.run_case("word_screenshot_identity_hold")
        self.assertIsNone(result)
        self.assertEqual(str(error), "word_screenshot_identity_hold")


if __name__ == "__main__":
    unittest.main()
