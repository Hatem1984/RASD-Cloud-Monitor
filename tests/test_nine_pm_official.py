"""Offline one-time pilot guard tests: no network, no Gmail, no private ledger."""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import rasd_nine_pm_official as target


class NinePmPilotSafety(unittest.TestCase):
    def environment(self):
        return {
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW_REF": target.EXPECTED_WORKFLOW,
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_RUN_ID": "1234",
        }

    def test_exact_nine_pm_cairo_allowed_only_on_october_22(self):
        with patch.dict(os.environ, self.environment(), clear=True):
            target.check_dispatch_clock(
                datetime(2026, 10, 22, 18, 0, tzinfo=timezone.utc))
            for moment in [
                datetime(2026, 10, 22, 17, 59, tzinfo=timezone.utc),
                datetime(2026, 10, 22, 18, 30, tzinfo=timezone.utc),
                datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc),
                datetime(2027, 10, 22, 18, 0, tzinfo=timezone.utc),
            ]:
                with self.subTest(moment=moment):
                    with self.assertRaisesRegex(RuntimeError, "window_expired"):
                        target.check_dispatch_clock(moment)

    def test_manual_dispatch_and_retries_can_never_send(self):
        for key, value in [
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("GITHUB_EVENT_NAME", "push"),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_REF", "refs/heads/gate9pm-someone"),
            ("GITHUB_WORKFLOW_REF", "untrusted"),
            ("GITHUB_REPOSITORY", "someone/else"),
            ("GITHUB_RUN_ID", "untrusted"),
        ]:
            env = self.environment()
            env[key] = value
            with patch.dict(os.environ, env, clear=True):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(RuntimeError):
                        target.check_dispatch_clock(
                            datetime(2026, 10, 22, 18, 1, tzinfo=timezone.utc))

    def test_offline_proof_never_accesses_private_mail_or_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fake.docx"
            path.write_bytes(b"fake_offline_docx_no_real_mail")
            story = {"id": "3" * 64, "url": target.SOURCE_URL}
            with patch.object(target, "render_official_sample", return_value=(path, story)):
                with patch.object(target, "protected_credentials",
                                  side_effect=AssertionError("no protected credentials")):
                    with patch.object(target, "send_one_word",
                                      side_effect=AssertionError("no email")):
                        with patch("sys.argv", ["rasd_nine_pm_official.py", "--mode", "proof"]):
                            target.main()

    def test_official_source_is_not_mistaken_for_today_newsroom_feed(self):
        self.assertEqual(target.SOURCE_DAY.isoformat(), "2026-10-21")
        self.assertEqual(target.PILOT_DAY.isoformat(), "2026-10-22")
        self.assertEqual(
            target.canonical_official_article(target.SOURCE_URL),
            target.SOURCE_URL,
        )


if __name__ == "__main__":
    unittest.main()
