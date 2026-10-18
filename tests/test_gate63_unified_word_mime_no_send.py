"""Gate63: test the NEW unified Word MIME in-memory with synthetic publisher images.

Never a real email, real Gmail identity or source-coverage approval.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from gate63_unified_mail_no_send import no_send_unified_mime_preflight
from test_gate40_unified_ministry_word import DAY, FakeDriver, execute


def make_report(tmp):
    FakeDriver.urls = ["https://mped.gov.eg/singlenews?id=7269&lang=ar"]
    FakeDriver.blocked = set()
    FakeDriver.offday = set()
    FakeDriver.bad_image = set()
    FakeDriver.list_changed = False
    FakeDriver.pages = None
    audit = execute(tmp)
    word = Path(tmp) / "out" / f"RASD-Unified-{DAY.isoformat()}.docx"
    assert audit["status"] == "READY_QA_ONLY", audit
    assert word.exists()
    return audit, word


class UnifiedWordMimeNoSendTests(unittest.TestCase):
    def test_verified_unified_word_one_mime_attachment_byte_equal_no_smtp(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            with patch("smtplib.SMTP_SSL") as smtp:
                result = no_send_unified_mime_preflight(audit, word, DAY)
            smtp.assert_not_called()
            self.assertEqual(result["status"], "UNIFIED_WORD_MIME_NO_SEND_PREFLIGHT_ONLY")
            self.assertEqual(result["date_cairo"], DAY.isoformat())
            self.assertEqual(result["original_source_count"], 3)
            self.assertEqual(result["attachment_count"], 1)
            self.assertEqual(result["attachment_sha256"],
                             hashlib.sha256(word.read_bytes()).hexdigest())
            self.assertEqual(result["attachment_bytes"], word.stat().st_size)
            for name in (
                "smtp_used", "private_ledger_touched", "gmail_authenticated",
                "human_review_inferred", "production_delivery_approved",
                "email_sent", "scheduler_enabled",
            ):
                self.assertIs(result[name], False, name)

    def test_strict_valid_empty_rss_is_healthy_not_false_outage(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            audit["source_health"][0]["verified_links"] = 0
            audit["source_health"][1]["verified_links"] = 0
            result = no_send_unified_mime_preflight(audit, word, DAY)
            self.assertEqual(result["original_source_count"], 3)
            self.assertFalse(result["email_sent"])

    def test_official_ministry_must_still_have_a_discovered_original_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            audit["source_health"][2]["verified_links"] = 0
            with self.assertRaisesRegex(ValueError, "original_source_incomplete"):
                no_send_unified_mime_preflight(audit, word, DAY)

    def test_unverified_source_full_report_refused_before_mime(self):
        for change in (
            {"status": "HOLD"},
            {"coverage": "DEGRADED"},
            {"all_sources_healthy": False},
            {"word_images_verified": False},
            {"word_created": False},
            {"official_pagination_complete": False},
            {"production_15_item_cap_intact": False},
            {"email_sent": True},
            {"scheduler_enabled": True},
            {"private_storage_used": True},
            {"final_report_published": True},
            {"source_added_to_production": True},
            {"production_sources_changed": True},
            {"keywords_changed": True},
        ):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                audit, word = make_report(tmp)
                audit.update(change)
                with self.assertRaisesRegex(ValueError, "stage2_not_qualified"):
                    no_send_unified_mime_preflight(audit, word, DAY)

    def test_wrong_original_source_endpoint_or_health_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            health = audit["source_health"]
            audit["source_health"] = health[:2]
            with self.assertRaisesRegex(ValueError, "original_source_incomplete"):
                no_send_unified_mime_preflight(audit, word, DAY)
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            audit["source_health"][1]["status"] = "failed"
            with self.assertRaisesRegex(ValueError, "original_source_incomplete"):
                no_send_unified_mime_preflight(audit, word, DAY)

    def test_all_picture_missing_or_wrong_article_count_rejected(self):
        for change in (
            {"selected_unique_articles": 3},
            {"screenshots_verified": 1},
            {"screenshots_missing": 1},
            {"rss_source_count": 1},
            {"official_source_count": 2},
        ):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                audit, word = make_report(tmp)
                audit.update(change)
                with self.assertRaisesRegex(ValueError, "article_evidence_incomplete"):
                    no_send_unified_mime_preflight(audit, word, DAY)

    def test_wrong_original_word_filename_or_non_docx_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            moved = word.with_name("RASD-Daily-2026-10-17.docx")
            word.rename(moved)
            with self.assertRaisesRegex(ValueError, "word_invalid"):
                no_send_unified_mime_preflight(audit, moved, DAY)
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            word.write_bytes(b"wrong-docx" * 500)
            with self.assertRaisesRegex(ValueError, "word_not_docx"):
                no_send_unified_mime_preflight(audit, word, DAY)

    def test_current_or_future_day_is_not_full_cairo_day(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            with self.assertRaisesRegex(ValueError, "requires_complete_cairo_day"):
                no_send_unified_mime_preflight(audit, word, date(2099, 1, 1))

    def test_different_report_day_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit, word = make_report(tmp)
            with self.assertRaisesRegex(ValueError, "audit_day_mismatch"):
                no_send_unified_mime_preflight(audit, word, date(2026, 10, 16))

    def test_no_legacy_gmail_implementation_or_real_address_or_network_apis(self):
        src = (Path(__file__).resolve().parents[1] /
               "gate63_unified_mail_no_send.py").read_text(encoding="utf-8")
        for forbidden in ("smtplib", "gmail_submit(", "PrivateGitHubLedger",
                          "urlopen(", "requests.", "boto3", "schedule:",
                          "smtp_factory", "RASD_GMAIL_APP_PASSWORD"):
            self.assertNotIn(forbidden, src)
        self.assertIn("example.invalid", src)
        self.assertIn("RASD-Unified-", src)


if __name__ == "__main__":
    unittest.main()
