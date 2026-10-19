"""Gate64: actual unified Stage2 Word reaches MIME no-send in owner QA workflow.

Fixtures are synthetic. They never count as a second real Cairo day or owner
review, and no test sends an email or uses an SMTP credential.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from gate64_stage2_live_mime_no_send import stage2_live_no_send_mime_check
from test_gate63_unified_word_mime_no_send import DAY, make_report

TODAY_AFTER_FIXTURE = DAY + timedelta(days=1)
WORKFLOW = (
    Path(__file__).resolve().parents[1] /
    ".github/workflows/report-unified-ministry-manual.yml"
)


class Stage2ActualWordNoSendBridgeTests(unittest.TestCase):
    def test_full_yesterday_actual_original_fixture_word_mime_rehearsed(self):
        with tempfile.TemporaryDirectory() as temp:
            audit, word = make_report(temp)
            with patch("smtplib.SMTP_SSL") as smtp:
                result = stage2_live_no_send_mime_check(
                    audit, word.parent, requested_window="yesterday",
                    today_cairo=TODAY_AFTER_FIXTURE,
                )
            smtp.assert_not_called()
            self.assertEqual(result["status"], "UNIFIED_WORD_MIME_NO_SEND_QA_ONLY")
            self.assertTrue(result["mime_rehearsed"])
            self.assertEqual(result["attachment_count"], 1)
            self.assertEqual(result["article_count"], audit["selected_unique_articles"])
            self.assertEqual(result["original_source_count"], 3)
            for key in ("smtp_used", "email_sent", "production_delivery_approved"):
                self.assertIs(result[key], False)
            self.assertFalse("attachment_sha256" in result)
            self.assertFalse("attachment_bytes" in result)

    def test_explicit_source_hold_skips_and_keeps_absence_of_report(self):
        with tempfile.TemporaryDirectory() as temp:
            audit, word = make_report(temp)
            word.unlink()
            audit.update(status="HOLD", word_created=False,
                         all_sources_healthy=False, coverage="DEGRADED")
            with patch("gate64_stage2_live_mime_no_send.no_send_unified_mime_preflight") as mime:
                result = stage2_live_no_send_mime_check(
                    audit, word.parent, requested_window="yesterday",
                    today_cairo=TODAY_AFTER_FIXTURE,
                )
                mime.assert_not_called()
            self.assertEqual(result["status"], "SKIPPED_SOURCE_OR_PROOF_HOLD")
            self.assertFalse(result["mime_rehearsed"])
            self.assertFalse(result["email_sent"])

    def test_source_hold_cannot_skip_if_old_word_leaked(self):
        with tempfile.TemporaryDirectory() as temp:
            audit, word = make_report(temp)
            audit.update(status="HOLD", word_created=False)
            with self.assertRaisesRegex(ValueError, "hold_with_unapproved_word"):
                stage2_live_no_send_mime_check(
                    audit, word.parent, requested_window="yesterday",
                    today_cairo=TODAY_AFTER_FIXTURE,
                )

    def test_partial_today_is_explicit_skip_not_full_day_mime_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            audit, word = make_report(temp)
            with patch("gate64_stage2_live_mime_no_send.no_send_unified_mime_preflight") as mime:
                result = stage2_live_no_send_mime_check(
                    audit, word.parent, requested_window="today",
                    today_cairo=DAY,
                )
                mime.assert_not_called()
            self.assertEqual(result["status"], "SKIPPED_PARTIAL_CAIRO_DAY")
            self.assertFalse(result["mime_rehearsed"])

    def test_duplicate_ambiguous_or_wrong_day_original_docx_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            audit, word = make_report(temp)
            (word.parent / "RASD-Unified-2026-10-16.docx").write_bytes(
                word.read_bytes())
            with self.assertRaisesRegex(ValueError, "missing_or_ambiguous"):
                stage2_live_no_send_mime_check(
                    audit, word.parent, requested_window="yesterday",
                    today_cairo=TODAY_AFTER_FIXTURE,
                )
        with tempfile.TemporaryDirectory() as temp:
            audit, word = make_report(temp)
            word.rename(word.with_name("RASD-Unified-2026-10-16.docx"))
            with self.assertRaisesRegex(ValueError, "day_identity_mismatch"):
                stage2_live_no_send_mime_check(
                    audit, word.parent, requested_window="yesterday",
                    today_cairo=TODAY_AFTER_FIXTURE,
                )

    def test_timestamp_mode_and_explicit_delivery_flags_are_enforced(self):
        for updates in (
            {"target_date_cairo": "2026-10-18"},
            {"email_sent": True},
            {"scheduler_enabled": True},
            {"source_added_to_production": True},
            {"private_storage_used": True},
            {"mode": "legacy_rss_only"},
        ):
            with self.subTest(updates=updates), tempfile.TemporaryDirectory() as temp:
                audit, word = make_report(temp)
                audit.update(updates)
                with self.assertRaisesRegex(ValueError, "source_day_or_safety_mismatch"):
                    stage2_live_no_send_mime_check(
                        audit, word.parent, requested_window="yesterday",
                        today_cairo=TODAY_AFTER_FIXTURE,
                    )
        with tempfile.TemporaryDirectory() as temp:
            audit, word = make_report(temp)
            with self.assertRaisesRegex(ValueError, "invalid_manual_window"):
                stage2_live_no_send_mime_check(
                    audit, word.parent, requested_window="tomorrow",
                    today_cairo=TODAY_AFTER_FIXTURE,
                )

    def test_mime_integrity_violation_is_not_silently_approved(self):
        with tempfile.TemporaryDirectory() as temp:
            audit, word = make_report(temp)
            with patch("gate64_stage2_live_mime_no_send.no_send_unified_mime_preflight",
                       return_value={
                           "status": "UNIFIED_WORD_MIME_NO_SEND_PREFLIGHT_ONLY",
                           "attachment_count": 1,
                           "article_count": audit["selected_unique_articles"],
                           "original_source_count": 3,
                           "date_cairo": DAY.isoformat(),
                           "smtp_used": True,
                           "email_sent": False,
                           "private_ledger_touched": False,
                           "gmail_authenticated": False,
                           "production_delivery_approved": False,
                           "human_review_inferred": False,
                           "scheduler_enabled": False,
                       }):
                with self.assertRaisesRegex(ValueError, "mime_invariants_failed"):
                    stage2_live_no_send_mime_check(
                        audit, word.parent, requested_window="yesterday",
                        today_cairo=TODAY_AFTER_FIXTURE,
                    )

    def test_real_manual_owner_workflow_rehearses_after_ciphertext_packing(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", content)
        self.assertNotIn("schedule:", content)
        self.assertIn("github.actor == 'Hatem1984'", content)
        self.assertIn('from gate64_stage2_live_mime_no_send import', content)
        pack_at = content.index("receipt = pack_owner_review(")
        mime_at = content.index("mime_result = stage2_live_no_send_mime_check(")
        verdict_at = content.index("verdict = stage2_manual_machine_verdict(")
        self.assertLess(pack_at, mime_at)
        self.assertLess(verdict_at, mime_at)
        self.assertIn("if mime_failed:", content)
        self.assertIn("OWNER_CIPHERTEXT_PRESERVED", content)
        self.assertIn("if: ${{ always() }}", content)
        self.assertIn("path: ${{ runner.temp }}/rasd-g43-owner-encrypted.json", content)
        self.assertIn("retention-days: 1", content)
        self.assertNotIn("RASD_GMAIL_APP_PASSWORD", content)
        self.assertNotIn("smtplib", content)
        self.assertIn("RASD_STAGE2_SOURCE_OR_REPORT_HOLD_NOT_ACCEPTED", content)

    def test_new_bridge_never_imports_transport_storage_or_private_auth(self):
        content = (Path(__file__).resolve().parents[1] /
                   "gate64_stage2_live_mime_no_send.py").read_text()
        for forbidden in (
            "gmail_submit(", "smtplib", "requests.", "urlopen(",
            "boto3", "PrivateGitHubLedger", "RASD_GMAIL_APP_PASSWORD",
            "create_bucket", "schedule:", "send_message(",
        ):
            self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
