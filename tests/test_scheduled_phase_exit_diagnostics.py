"""Purely static QA: scheduler status diagnostics must never change dispatch safety."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    (".github/workflows/rasd-scheduled.yml", "recovery_exit"),
    (".github/workflows/rasd-cloudflare-dispatch.yml", "rollup_exit"),
    (".github/workflows/rasd-schedule-backup.yml", "daily_exit"),
)


class ScheduledPhaseExitDiagnostics(unittest.TestCase):
    def test_existing_two_phase_calls_and_hard_failure_preserved(self):
        for path, recovery_var in WORKFLOWS:
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                interval_call = "python scheduled_rasd.py --mode interval || interval_exit=$?"
                recovery_call = (
                    "python scheduled_rasd.py --mode rollup_recovery || "
                    + recovery_var + "=$?"
                )
                interval_marker = 'echo "RASD_INTERVAL_PHASE_EXIT=$interval_exit"'
                recovery_marker = (
                    'echo "RASD_ROLLUP_RECOVERY_PHASE_EXIT=$'
                    + recovery_var + '"'
                )
                guard = (
                    'if [ "$interval_exit" -ne 0 ] || [ "$'
                    + recovery_var + '" -ne 0 ]; then'
                )
                for needle in (interval_call, recovery_call, interval_marker,
                               recovery_marker, guard):
                    self.assertEqual(text.count(needle), 1, (path, needle))
                self.assertIn("exit 1", text)
                positions = [text.index(v) for v in (
                    interval_call, interval_marker, recovery_call, recovery_marker,
                    guard)]
                self.assertEqual(positions, sorted(positions))
                self.assertIn("cancel-in-progress: false", text)

    def test_diagnostics_contain_only_numeric_exit_variables(self):
        for path, recovery_var in WORKFLOWS:
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                new_lines = [
                    line.strip() for line in text.splitlines()
                    if "RASD_INTERVAL_PHASE_EXIT=" in line
                    or "RASD_ROLLUP_RECOVERY_PHASE_EXIT=" in line
                ]
                self.assertEqual(new_lines, [
                    'echo "RASD_INTERVAL_PHASE_EXIT=$interval_exit"',
                    'echo "RASD_ROLLUP_RECOVERY_PHASE_EXIT=$'
                    + recovery_var + '"',
                ])
                self.assertNotIn("${{", "\n".join(new_lines))


if __name__ == "__main__":
    unittest.main()
