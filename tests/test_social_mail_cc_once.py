"""No-network security and Word test for the owner social CC delivery pilot."""
from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from docx import Document

import rasd_social_mail_test_once as target


def approved_fake_env() -> dict[str, str]:
    return {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
        "GITHUB_WORKFLOW_REF": target.WORKFLOW_REF,
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR": "Hatem1984",
        "GITHUB_RUN_ID": "12345",
        "RASD_SOCIAL_TEST_APPROVAL": target.OWNER_CONFIRM,
        "RASD_REPORT_CC_REQUIRED": "true",
        "RASD_REPORT_CC": "approved-test-copy@example.invalid",
    }


class SocialMailOnlyTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 14, 0, tzinfo=timezone.utc)

    def test_real_existing_rasd_builder_produces_honest_test_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = target.make_social_test_word(Path(tmp), self.now)
            doc = Document(p)
            text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("اختبار إرسال تقرير السوشيال من رصد", text)
            self.assertIn("لا توجد مواد موثقة", text)
            self.assertIn("فيسبوك: تصريح الوصول غير متوفر", text)
            self.assertEqual(len(doc.inline_shapes), 0)
            for section in doc.sections:
                footer = "\n".join(p.text for p in section.footer.paragraphs)
                self.assertIn("اختبار تسليم من نظام رصد", footer)
                self.assertNotIn("معاينة محلية غير مرسلة", footer)
            self.assertIn("EMAIL-TEST-UNVERIFIED", p.name)
            self.assertGreater(p.stat().st_size, 3000)

    def test_default_is_offline_and_cannot_touch_credentials_or_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            credential = Mock(side_effect=AssertionError("credentials read"))
            transport = Mock(side_effect=AssertionError("SMTP attempted"))
            got = target.run(mode="dry_run_no_network", now=self.now,
                             directory=Path(tmp), environment={},
                             credentials=credential, transport=transport)
            self.assertEqual(got["status"], "DRY_RUN_NO_NETWORK")
            self.assertFalse(got["smtp_accepted"])
            self.assertFalse(got["private_cas_mutated"])
            self.assertTrue(got["cc_requested"])
            credential.assert_not_called()
            transport.assert_not_called()

    def test_all_production_manual_approval_gates_fail_closed(self):
        env = approved_fake_env()
        target.require_manual_send_context(env)
        for key, bad in (
            ("GITHUB_EVENT_NAME", "push"),
            ("GITHUB_REF", "refs/heads/feature"),
            ("GITHUB_ACTOR", "another"),
            ("GITHUB_REPOSITORY", "other/repo"),
            ("GITHUB_WORKFLOW_REF", "other/workflow"),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_RUN_ID", "abc"),
            ("RASD_SOCIAL_TEST_APPROVAL", "no"),
            ("RASD_REPORT_CC_REQUIRED", "false"),
            ("RASD_REPORT_CC", ""),
        ):
            with self.subTest(key=key):
                tampered = dict(env, **{key: bad})
                with self.assertRaisesRegex(RuntimeError, "approval_or_cc_hold"):
                    target.require_manual_send_context(tampered)

    def test_single_cas_then_smtp_then_receipt_and_duplicate_holds(self):
        state = {"schema_version": 2, "entries": {},
                 "approved_recipient_sha256": "a" * 64}
        ledger = Mock()
        ledger.read.side_effect = lambda: (copy.deepcopy(state), "old-sha")
        def save(payload, previous):
            self.assertEqual(previous, "old-sha")
            state.clear()
            state.update(copy.deepcopy(payload))
        ledger.write.side_effect = save
        transport = Mock(return_value=f"<rasd-{target.TEST_KEY}@gmail.com>")
        credentials = Mock(return_value=(
            "rasd-sender@gmail.com", "primary@example.invalid",
            "dummy-app-password", ledger))
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                target, "approved_report_copy",
                return_value="approved-test-copy@example.invalid"):
            one = target.run(
                mode="send_once", now=self.now, directory=Path(tmp),
                environment=approved_fake_env(),
                credentials=credentials, transport=transport)
            self.assertTrue(one["smtp_accepted"])
            self.assertFalse(one["primary_inbox_verified"])
            self.assertFalse(one["cc_inbox_verified"])
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(state["entries"][target.TEST_KEY]["kind"],
                             "social_transport_test_only")
            self.assertNotIn("news", state["entries"][target.TEST_KEY])
            ledger.mark_smtp_accepted.assert_called_once()
            two = target.run(
                mode="send_once", now=self.now, directory=Path(tmp),
                environment=approved_fake_env(),
                credentials=credentials, transport=transport)
            self.assertEqual(two["status"], "HOLD_TEST_ALREADY_RESERVED_OR_SENT")
            self.assertFalse(two["smtp_accepted"])
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(ledger.write.call_count, 1)

    def test_failed_cc_validation_prevents_reservation_and_smtp(self):
        ledger = Mock()
        credentials = Mock(return_value=(
            "rasd-sender@gmail.com", "primary@example.invalid",
            "dummy-app-password", ledger))
        transport = Mock()
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                target, "approved_report_copy", return_value=None):
            with self.assertRaisesRegex(RuntimeError,
                                        "approved_cc_required_hold"):
                target.run(
                    mode="send_once", now=self.now, directory=Path(tmp),
                    environment=approved_fake_env(),
                    credentials=credentials, transport=transport)
        ledger.read.assert_not_called()
        transport.assert_not_called()

    def test_no_implicit_send_on_unknown_mode_and_missing_output(self):
        with self.assertRaises(ValueError):
            target.run(mode="send", now=self.now, directory=Path("unused"))
        with self.assertRaises(ValueError):
            target.run(mode="dry_run_no_network", now=self.now)


if __name__ == "__main__":
    unittest.main()
