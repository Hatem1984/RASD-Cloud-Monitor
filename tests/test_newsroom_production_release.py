"""Owner-approved 30-minute newsroom release protections (offline, zero mail)."""
from pathlib import Path
import unittest


ROOT=Path(__file__).resolve().parents[1]

class NewsroomDeploymentSafety(unittest.TestCase):
    def test_schedule_only_main_protected_environment_and_pause_switch(self):
        workflow=(ROOT/".github/workflows/rasd-scheduled.yml").read_text("utf-8")
        self.assertIn("vars.RASD_AUTOMATION_PAUSED != 'true'",workflow)
        self.assertIn("github.event_name == 'schedule'",workflow)
        self.assertIn("github.ref == 'refs/heads/main'",workflow)
        self.assertIn("github.actor == 'Hatem1984'",workflow)
        self.assertIn("github.event.head_commit.message == 'RASD-OWNER-DAILY-2026-10-23'",workflow)
        self.assertIn("environment: rasd-production",workflow)
        self.assertIn("RASD_AUTOMATION_ENABLED: 'true'",workflow)
        self.assertIn("RASD_PRIVATE_LEDGER_TOKEN: ${{ secrets.RASD_PRIVATE_LEDGER_TOKEN }}",workflow)
        self.assertIn("RASD_GMAIL_APP_PASSWORD: ${{ secrets.RASD_GMAIL_APP_PASSWORD }}",workflow)
        self.assertIn("RASD_REPORT_TO: ${{ secrets.RASD_REPORT_TO }}",workflow)
        self.assertIn("python scheduled_rasd.py --mode \"$mode\"",workflow)
        self.assertIn("group: rasd-scheduled-monitor-private-ledger",workflow)
        self.assertIn("cancel-in-progress: false",workflow)
        self.assertIn("7,18,37,48 * * * *",workflow)

    def test_non_send_manual_preview_keeps_no_secrets(self):
        workflow=(ROOT/".github/workflows/rasd-scheduled.yml").read_text("utf-8")
        preview=workflow.split("  no-send-preview:",1)[1].split("  protected-scheduled-monitor:",1)[0]
        self.assertIn("if: github.event_name == 'workflow_dispatch'",preview)
        self.assertNotIn("secrets.",preview)
        self.assertIn("scheduled_rasd.py --mode dry_run",preview)

    def test_protected_worker_still_requires_exact_schedule_guard(self):
        from scheduled_rasd import require_github_scheduler,EXPECTED_WORKFLOW
        import os
        from unittest.mock import patch
        allowed={
            "GITHUB_EVENT_NAME":"schedule",
            "GITHUB_REF":"refs/heads/main",
            "GITHUB_REPOSITORY":"Hatem1984/RASD-Cloud-Monitor",
            "GITHUB_RUN_ATTEMPT":"1",
            "GITHUB_WORKFLOW_REF":EXPECTED_WORKFLOW,
            "RASD_JOB_CRON":"7,18,37,48 * * * *",
            "GITHUB_RUN_ID":"12345",
            "RASD_AUTOMATION_ENABLED":"true",
        }
        with patch.dict(os.environ,allowed,clear=True):
            require_github_scheduler()
            os.environ["GITHUB_EVENT_NAME"]="workflow_dispatch"
            with self.assertRaises(RuntimeError):
                require_github_scheduler()


if __name__=="__main__":
    unittest.main()
