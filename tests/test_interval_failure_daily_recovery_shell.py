"""Offline proof that an interval error cannot suppress overdue 22:00 recovery."""
import os
import subprocess
import textwrap
import unittest
from pathlib import Path


class IndependentDailyRecovery(unittest.TestCase):
    def shell_block(self):
        workflow = Path(".github/workflows/rasd-scheduled.yml").read_text("utf-8")
        anchor = '          if [ "$mode" = interval ]; then'
        self.assertEqual(workflow.count(anchor), 1)
        script = workflow.split(anchor, 1)[1]
        script = anchor + script
        return textwrap.dedent(script)

    def run_case(self, interval_result, recovery_result):
        commands = """set -euo pipefail
mode=interval
python() {
  if [ "$3" = "interval" ]; then echo INTERVAL_ATTEMPTED; return "$INTERVAL_RESULT"; fi
  if [ "$3" = "rollup_recovery" ]; then echo DAILY_RECOVERY_ATTEMPTED; return "$RECOVERY_RESULT"; fi
  echo BAD_TEST_INVOCATION; return 100
}
"""
        env = dict(os.environ, INTERVAL_RESULT=str(interval_result),
                   RECOVERY_RESULT=str(recovery_result))
        return subprocess.run(["bash", "-c", commands + self.shell_block()],
                              capture_output=True, text=True, env=env,
                              check=False)

    def test_interval_failure_does_not_skip_daily(self):
        output = self.run_case(7, 0)
        self.assertNotEqual(output.returncode, 0)
        self.assertIn("INTERVAL_ATTEMPTED", output.stdout)
        self.assertIn("DAILY_RECOVERY_ATTEMPTED", output.stdout)
        self.assertIn("RASD_SCHEDULED_INTERVAL_OR_DAILY_RECOVERY_HOLD", output.stdout)

    def test_daily_failure_keeps_failed_workflow(self):
        output = self.run_case(0, 9)
        self.assertNotEqual(output.returncode, 0)
        self.assertIn("DAILY_RECOVERY_ATTEMPTED", output.stdout)

    def test_both_success_remain_successful(self):
        output = self.run_case(0, 0)
        self.assertEqual(output.returncode, 0)
        self.assertIn("DAILY_RECOVERY_ATTEMPTED", output.stdout)

    def test_recovery_never_masks_two_failures(self):
        output = self.run_case(6, 9)
        self.assertNotEqual(output.returncode, 0)
        self.assertIn("DAILY_RECOVERY_ATTEMPTED", output.stdout)


if __name__ == "__main__":
    unittest.main()
