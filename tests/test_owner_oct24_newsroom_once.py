"""Owner Oct24 newsroom catch-up: authorized marker, past-day label, no other push."""
from datetime import datetime, timezone
import os
import unittest
from unittest.mock import patch
import scheduled_rasd as worker


class Oct24NewsroomOwnerOneoff(unittest.TestCase):
    def env(self):
        return {
            "GITHUB_EVENT_NAME":"push",
            "GITHUB_ACTOR":"Hatem1984",
            "GITHUB_REF":"refs/heads/main",
            "GITHUB_REPOSITORY":"Hatem1984/RASD-Cloud-Monitor",
            "GITHUB_RUN_ATTEMPT":"1",
            "GITHUB_WORKFLOW_REF":worker.EXPECTED_WORKFLOW,
            "RASD_AUTOMATION_ENABLED":"true",
            "GITHUB_RUN_ID":"1122334",
            "RASD_JOB_CRON":"",
            "RASD_OWNER_PUSH_CONFIRM":"RASD-OWNER-NEWSROOM-2026-10-24",
        }

    def test_accepts_owner_only_on_requested_day_in_window(self):
        with patch.dict(os.environ,self.env(),clear=True), patch.object(worker,"datetime") as d:
            d.now.return_value = datetime(2026,10,24,11,35,tzinfo=timezone.utc)
            worker.require_github_scheduler()
            d.now.return_value = datetime(2026,10,24,18,0,tzinfo=timezone.utc)
            with self.assertRaisesRegex(RuntimeError,"outside_cairo_date_window"):
                worker.require_github_scheduler()

    def test_push_cannot_trigger_unrelated_periodic_or_normal_daily_send(self):
        with patch.dict(os.environ,self.env(),clear=True), patch.object(
            worker,"require_github_scheduler"
        ), patch.object(worker,"protected_credentials") as creds:
            for mode in ("interval","rollup","rollup_recovery","rollup_owner_once"):
                with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                    worker.run_scheduled(mode,datetime(
                        2026,10,24,11,35,tzinfo=timezone.utc))
            creds.assert_not_called()

    def test_unapproved_historical_age_cannot_affect_normal_24h_periodic(self):
        with self.assertRaisesRegex(ValueError,"unapproved_newsroom_lookback"):
            worker.discover_interval_news(
                {"feeds":[]},datetime(2026,10,24,11,30,tzinfo=timezone.utc),
                age_hours=96)


if __name__ == "__main__":
    unittest.main()
