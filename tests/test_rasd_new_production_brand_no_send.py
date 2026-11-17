"""RASD-only identity for NEW outbound documents and email.

Historical received MA'AL-named files remain untouched: these tests only
inspect current production authoring, using offline MIME and original Word
helpers. Never send, read secrets, or modify receipt/CAS state.
"""
from pathlib import Path
import unittest

from digest_mailer import build_digest_message


class NewRASDIdentityNoSend(unittest.TestCase):
    def test_production_issued_subjects_do_not_mention_separate_project(self):
        for path in (
            "scheduled_rasd.py", "daily_report.py",
            "cloud_proof_report.py", "digest_mailer.py",
        ):
            source = Path(path).read_text(encoding="utf-8")
            self.assertNotIn("مآل", source, path)
        scheduled = Path("scheduled_rasd.py").read_text(encoding="utf-8")
        self.assertIn("رصد | أخبار جديدة من الفحص الدوري", scheduled)
        self.assertIn("رصد | التقرير المجمع للأخبار المرسلة", scheduled)
        self.assertIn("رصد | تقرير حالة المتابعة النصف ساعية", scheduled)
        self.assertIn("رصد | تقرير حالة المتابعة: لا أخبار", scheduled)
        self.assertIn("رصد | تقرير حالة: أخبار مُرسلة", scheduled)

    def test_manual_gmail_message_subject_and_body_use_only_rasd(self):
        report = {
            "email_sent": False, "scheduler_enabled": False,
            "private_state_used": False, "coverage": "HEALTHY",
            "status": "READY", "articles": 1, "screenshots_verified": 1,
            "screenshots_missing": 0, "word_created": True,
        }
        msg = build_digest_message(report, "2026-11-17", "a"*24,
                                   b"offline-not-a-real-Word",
                                   "fixture@gmail.com")
        self.assertEqual(msg["Subject"],
                         "رصد | التقرير الإخباري اليومي | 2026-11-17")
        self.assertIn("تقرير رصد الإخباري", msg.get_body(
            preferencelist=("plain",)).get_content())
        self.assertEqual(msg["To"], "fixture@gmail.com")
        self.assertEqual(msg["X-RASD-Digest-ID"], "a"*24)
        self.assertEqual(len(list(msg.iter_attachments())), 1)

    def test_legacy_already_sent_archive_conversion_still_supported(self):
        # Do not rewrite historic private delivery receipts or original
        # publisher screenshots; old Word readback may contain this prefix.
        source = Path("rasd_ministry_visual_layout.py").read_text("utf-8")
        self.assertIn('title.startswith("مآل | ")', source)
        self.assertIn('display_title = ("رصد | "', source)
        ledger = Path("delivery_bridge.py").read_text("utf-8")
        self.assertIn("PRIVATE_REPO", ledger)
        self.assertIn("reserved_at", ledger)


if __name__ == "__main__":
    unittest.main()
