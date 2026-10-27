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


    def test_reviewed_daily_archive_hold_codes_are_safe_to_log(self):
        # Fixed low-information status names, never raw exception messages.
        from scheduled_rasd import safe_scheduled_hold_reason
        for code in (
            "daily_imap_login_hold",
            "daily_imap_archive_unavailable_hold",
            "daily_sent_message_not_found",
            "daily_sent_attachment_identity_hold",
            "daily_consolidation_incomplete_private_ledger",
            "daily_consolidated_original_digest_hold",
        ):
            with self.subTest(code=code):
                self.assertEqual(safe_scheduled_hold_reason(RuntimeError(code)), code)

    def test_arbitrary_private_exception_text_remains_redacted(self):
        from scheduled_rasd import safe_scheduled_hold_reason
        for error in (
            RuntimeError("daily_imap_login_hold: private-account@example.invalid"),
            RuntimeError("https://publisher.example.invalid/secret"),
            ValueError("token=never-print-this"),
        ):
            self.assertEqual(safe_scheduled_hold_reason(error), "other_held_failure")


if __name__ == "__main__":
    unittest.main()
