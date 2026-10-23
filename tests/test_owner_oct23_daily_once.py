"""Date-locked, owner-authenticated Oct23 once-only daily delivery guards."""
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
import scheduled_rasd as rasd

class OwnerOct23DailyAcceptance(unittest.TestCase):
    def credentials(self):
        return {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
            "GITHUB_ACTOR": "Hatem1984",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW_REF": rasd.EXPECTED_WORKFLOW,
            "GITHUB_RUN_ID": "123456789",
            "RASD_AUTOMATION_ENABLED": "true",
            "RASD_JOB_CRON": "",
            "RASD_OWNER_PUSH_CONFIRM": "RASD-OWNER-DAILY-2026-10-23",
        }

    def test_exact_owner_signal_allows_only_one_cairo_hour(self):
        with patch.dict(os.environ, self.credentials(), clear=True), patch.object(rasd, "datetime") as live_clock:
            live_clock.now.return_value = datetime(2026, 10, 23, 19, 30, tzinfo=timezone.utc)
            rasd.require_github_scheduler()
            live_clock.now.return_value = datetime(2026, 10, 23, 20, 0, tzinfo=timezone.utc)
            with self.assertRaisesRegex(RuntimeError, "outside_cairo"):
                rasd.require_github_scheduler()
            live_clock.now.return_value = datetime(2026, 10, 24, 19, 30, tzinfo=timezone.utc)
            with self.assertRaises(RuntimeError):
                rasd.require_github_scheduler()

    def test_wrong_actor_marker_repo_attempt_and_manual_are_rejected(self):
        for key, value in [
            ("GITHUB_ACTOR", "attacker"),
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("RASD_OWNER_PUSH_CONFIRM", "wrong-marker"),
            ("GITHUB_REF", "refs/heads/test"),
            ("GITHUB_REPOSITORY", "other/repo"),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_RUN_ID", "not-a-run"),
        ]:
            env = self.credentials()
            env[key] = value
            with self.subTest(key=key), patch.dict(os.environ, env, clear=True), patch.object(rasd, "datetime") as clock:
                clock.now.return_value = datetime(2026, 10, 23, 19, 30, tzinfo=timezone.utc)
                with self.assertRaises(RuntimeError):
                    rasd.require_github_scheduler()

    def test_owner_trigger_never_enables_interval_or_recovery(self):
        with patch.dict(os.environ, self.credentials(), clear=True), patch.object(rasd, "require_github_scheduler"):
            for mode in ("interval", "rollup", "rollup_recovery"):
                with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, "manual_or_push"):
                    rasd.run_scheduled(mode, datetime(2026, 10, 23, 19, 30, tzinfo=timezone.utc))

if __name__ == "__main__":
    unittest.main()
