"""No-network official-source daily delivery security tests.

Only mocked publisher/build/send fixtures; NO real owner email or secrets.
"""
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import rasd_official_daily as worker


class OfficialDailySecurity(unittest.TestCase):
    def trusted_env(self):
        return {
            "GITHUB_EVENT_NAME": "schedule",
            "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_WORKFLOW_REF": worker.OFFICIAL_WORKFLOW,
            "GITHUB_RUN_ID": "123456",
            "RASD_JOB_CRON": "0 19 22 10 *",
        }

    def test_one_off_owner_date_exact_cairo_clock(self):
        env = self.trusted_env()
        with patch.dict(os.environ, env, clear=True):
            for allowed_cron, clock in [
                ("0 19 22 10 *", datetime(2026, 10, 22, 19, tzinfo=timezone.utc)),
                ("30 19 22 10 *", datetime(2026, 10, 22, 19, 30, tzinfo=timezone.utc)),
                ("0 20 22 10 *", datetime(2026, 10, 22, 20, tzinfo=timezone.utc)),
            ]:
                os.environ["RASD_JOB_CRON"] = allowed_cron
                worker.require_official_scheduled_send(clock)
            os.environ["RASD_JOB_CRON"] = "0 19 22 10 *"
            for clock in [
                datetime(2026, 10, 22, 18, 59, tzinfo=timezone.utc),
                datetime(2026, 10, 22, 21, 0, tzinfo=timezone.utc),
                datetime(2027, 10, 22, 19, 0, tzinfo=timezone.utc),
            ]:
                with self.subTest(clock=clock):
                    with self.assertRaises(RuntimeError):
                        worker.require_official_scheduled_send(clock)

    def test_exact_owner_git_push_is_one_time_only(self):
        env = self.trusted_env()
        env.update({
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_ACTOR": "Hatem1984",
            "RASD_OWNER_PUSH_CONFIRM":
                "RASD-OWNER-ONCE-2026-10-22-VERIFIED-OFFICIAL-WORD",
            "RASD_JOB_CRON": "",
        })
        now = datetime(2026, 10, 22, 19, 8, tzinfo=timezone.utc)
        with patch.dict(os.environ, env, clear=True):
            worker.require_official_scheduled_send(now)
            for key, forbidden in [
                ("GITHUB_ACTOR", "another-user"),
                ("RASD_OWNER_PUSH_CONFIRM", "wrong-message"),
                ("GITHUB_RUN_ATTEMPT", "2"),
                ("GITHUB_REF", "refs/heads/untrusted"),
            ]:
                original = os.environ[key]
                os.environ[key] = forbidden
                with self.subTest(key=key):
                    with self.assertRaises(RuntimeError):
                        worker.require_official_scheduled_send(now)
                os.environ[key] = original
            with self.assertRaises(RuntimeError):
                worker.require_official_scheduled_send(
                    datetime(2026, 10, 23, 19, tzinfo=timezone.utc))

    def test_owner_visual_correction_requires_single_day_and_distinct_cas_key(self):
        env = self.trusted_env()
        env.update({
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_ACTOR": "Hatem1984",
            "RASD_JOB_CRON": "",
            "RASD_OWNER_PUSH_CONFIRM":
                "RASD-OWNER-VISUAL-CORRECTION-2026-10-22",
        })
        ledger = MagicMock()
        ledger.reserve.return_value = "reserved"
        clock = datetime(2026, 10, 22, 20, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "original.docx"
            file.write_bytes(b"mock_no_network")
            with patch.dict(os.environ, env, clear=True), \
                 patch.object(worker, "protected_credentials",
                              return_value=("sender@gmail.com", "approved@example.com",
                                            "mock-password", ledger)), \
                 patch.object(worker, "send_one_word", return_value="<test-corrected>") as mail:
                result = worker.run(
                    mode="send", output=Path(tmp), clock=clock,
                    builder=lambda *_args, **_kwargs:
                        (file, [{"id": "fixture"}]))
            self.assertEqual(result["count"], 1)
            self.assertEqual(
                ledger.reserve.call_args.args[0],
                worker.digest_key("official-ministry-original-daily:2026-10-22:visual-correction-v2"))
            self.assertIn("مصححة", mail.call_args.kwargs["subject"])
            self.assertIn("CORRECTED.docx", mail.call_args.args[0].name)
            self.assertEqual(ledger.mark_smtp_accepted.call_count, 1)
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError):
                    worker.require_official_scheduled_send(
                        datetime(2026, 10, 23, 20, tzinfo=timezone.utc))

    def test_manual_run_replay_and_other_repository_cannot_send(self):
        for key, value in [
            ("GITHUB_EVENT_NAME", "workflow_dispatch"),
            ("GITHUB_EVENT_NAME", "push"),
            ("GITHUB_REPOSITORY", "untrusted/repo"),
            ("GITHUB_REF", "refs/heads/gate75-test"),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_WORKFLOW_REF", "fake"),
            ("GITHUB_RUN_ID", "invalid"),
            ("RASD_JOB_CRON", "unexpected-cron"),
        ]:
            env = self.trusted_env()
            env[key] = value
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaises(RuntimeError):
                    worker.require_official_scheduled_send(
                        datetime(2026, 10, 22, 19, 0, tzinfo=timezone.utc))

    def test_future_recurring_schedule_requires_separate_opt_in(self):
        env = self.trusted_env()
        env["RASD_JOB_CRON"] = "0 19,20 * * *"
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "not_explicitly_scheduled"):
                worker.require_official_scheduled_send(
                    datetime(2026, 10, 23, 19, tzinfo=timezone.utc))
            os.environ["RASD_OFFICIAL_AUTOMATION_ENABLED"] = "true"
            worker.require_official_scheduled_send(
                datetime(2026, 10, 23, 19, tzinfo=timezone.utc))

    def test_proof_does_not_consult_private_ledger_or_smtp(self):
        with tempfile.TemporaryDirectory() as tmp:
            word = Path(tmp) / "mock.docx"
            word.write_bytes(b"offline-only")
            with patch.object(worker, "protected_credentials",
                              side_effect=AssertionError("private read")), \
                 patch.object(worker, "send_one_word",
                              side_effect=AssertionError("real SMTP")):
                result = worker.run(
                    mode="proof", output=Path(tmp),
                    clock=datetime(2026, 10, 22, 19, tzinfo=timezone.utc),
                    builder=lambda *_args, **_kwargs:
                        (word, [{"id": "offline-only"}]))
        self.assertFalse(result["smtp_accepted"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["source_scope"], "official_ministry_not_newsroom")

    def test_private_reservation_occurs_before_exactly_one_smtp(self):
        env = self.trusted_env()
        ledger = MagicMock()
        ledger.reserve.return_value = "reserved"
        call_order = []
        ledger.reserve.side_effect = lambda *_args: (
            call_order.append("reserve") or "reserved")
        ledger.mark_smtp_accepted.side_effect = lambda *_args: (
            call_order.append("complete"))
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, env, clear=True), \
             patch.object(worker, "protected_credentials",
                          return_value=("sender@gmail.com", "approved@example.com",
                                        "mock-secret", ledger)), \
             patch.object(worker, "send_one_word",
                          side_effect=lambda *_args, **_kwargs:
                              (call_order.append("smtp") or "<test-message>")) as mail:
            result = worker.run(
                mode="send", output=Path(tmp),
                clock=datetime(2026, 10, 22, 19, tzinfo=timezone.utc),
                builder=lambda *_args, **_kwargs:
                    (Path(tmp) / "no-real-file.docx", [{"id": "fixture"}]))
        self.assertEqual(call_order, ["reserve", "smtp", "complete"])
        self.assertTrue(result["smtp_accepted"])
        self.assertIn("نشـرة".replace("ـ", ""), mail.call_args.kwargs["subject"].replace("ـ", ""))

    def test_duplicate_private_state_blocks_smtp_even_if_word_ready(self):
        env = self.trusted_env()
        ledger = MagicMock()
        ledger.reserve.return_value = "already_reserved"
        with tempfile.TemporaryDirectory() as tmp, \
             patch.dict(os.environ, env, clear=True), \
             patch.object(worker, "protected_credentials",
                          return_value=("sender@gmail.com", "approved@example.com",
                                        "mock-secret", ledger)), \
             patch.object(worker, "send_one_word",
                          side_effect=AssertionError("duplicate sent")):
            with self.assertRaisesRegex(RuntimeError, "private_duplicate_hold"):
                worker.run(
                    mode="send", output=Path(tmp),
                    clock=datetime(2026, 10, 22, 19, tzinfo=timezone.utc),
                    builder=lambda *_args, **_kwargs:
                        (Path(tmp) / "no-real-file.docx", [{"id": "fixture"}]))

    def test_invalid_day_rejected_without_publisher_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "invalid_cairo_date"):
                worker.build_official_daily(
                    Path(tmp), target_date="2026-10-22")


if __name__ == "__main__":
    unittest.main()
