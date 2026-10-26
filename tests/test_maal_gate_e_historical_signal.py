"""MA'AL Gate E: offline end-to-end safeguards with synthetic page fixture."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from maal.decision_contracts import BusinessContext
from maal.impact_mvp import (
    BusinessDemoProfile, interpret_official_signal, write_demo_docx,
)
from official_ministry_source import SAMPLE
from monitor import article_id


class MaalOfficialHistoricalDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "original.jpg"
        photo = Image.effect_noise((1200, 1100), 85).convert("RGB")
        photo.save(self.image, format="JPEG", quality=89)
        self.receipt = {
            "status": "verified", "url": SAMPLE,
            "id": article_id(SAMPLE),
            "published_date_cairo": "2026-10-17",
            "headline": "وزير التخطيط يعرض برنامج التحول الاقتصادي الوطني",
            "sha256": hashlib.sha256(self.image.read_bytes()).hexdigest(),
        }
        self.body = (self.receipt["headline"] + " " +
                     "ناقش الوزير آلية ضمان تمويل مشروعات البنية التحتية. " * 12)
        self.profile = BusinessDemoProfile(
            BusinessContext("SYNTHETIC-TEST", "البنية التحتية", "مصر"),
            ("infrastructure_finance",), True)
        self.clock = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)

    def brief(self, **changes):
        return interpret_official_signal(changes.get("receipt", self.receipt),
                                         changes.get("body", self.body),
                                         changes.get("image", self.image),
                                         changes.get("profile", self.profile),
                                         checked_at=changes.get("clock", self.clock))

    def test_real_source_contract_demo_never_invents_time_money_or_action(self):
        output = self.brief()
        self.assertEqual(output["type"], "HISTORICAL_OFFICIAL_SOURCE_DEMONSTRATION")
        self.assertTrue(output["sample_company_is_synthetic"])
        self.assertTrue(output["decision_contract_validated"])
        self.assertEqual(output["facts_from_verified_inputs"][0]["publication_precision"], "date")
        self.assertIsNone(output["evidence"]["published_time"])
        self.assertEqual(output["evidence"]["publication_precision"], "DATE_ONLY")
        self.assertEqual(output["evidence"]["published_day_cairo"], "2026-10-17")
        self.assertIsNone(output["business_impact"]["quantified_impact"])
        self.assertFalse(output["external_actions_executed"])
        self.assertFalse(output["email_sent"])
        self.assertFalse(output["private_ledger_touched"])
        self.assertTrue(output["human_approval_required"])
        self.assertEqual(len(output["proposals_not_executed"]), 2)

    def test_not_verified_original_page_blocks_all_actions(self):
        with self.assertRaisesRegex(ValueError, "original_source_verification_required"):
            self.brief(receipt={**self.receipt, "status": "HOLD"})

    def test_mismatched_image_hash_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "original_screenshot_digest_mismatch"):
            self.brief(receipt={**self.receipt, "sha256": "0" * 64})

    def test_source_url_substitution_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unapproved_official_sample_url"):
            self.brief(receipt={**self.receipt,
                                "url": "https://untrusted.example/other"})

    def test_claim_cannot_be_supported_without_original_body_wording(self):
        with self.assertRaisesRegex(ValueError, "funding_signal_not_supported"):
            self.brief(body="الوزير تحدث عن خطط رياضية في اجتماع عام. " * 25)

    def test_publisher_timestamp_cannot_be_guessed(self):
        with self.assertRaisesRegex(ValueError, "original_date_only_not_verified"):
            self.brief(receipt={**self.receipt,
                                "published_date_cairo": "2026-10-17T09:00:00+03:00"})

    def test_real_company_baseline_cannot_be_claimed(self):
        with self.assertRaisesRegex(ValueError, "customer_baseline_required"):
            self.brief(profile=BusinessDemoProfile(
                BusinessContext("SYNTHETIC-TEST", "البنية التحتية", "مصر"),
                ("infrastructure_finance",), False))

    def test_unreviewed_sector_exposure_not_fabricated(self):
        with self.assertRaisesRegex(ValueError, "unreviewed_business_exposure"):
            self.brief(profile=BusinessDemoProfile(
                BusinessContext("SYNTHETIC-TEST", "عام", "مصر"),
                ("all-sectors",), True))

    def test_naive_observation_clock_rejected(self):
        with self.assertRaisesRegex(ValueError, "observation_time_must_be_aware"):
            self.brief(clock=datetime(2026, 10, 26, 12, 0))

    def test_date_only_word_binds_exact_capture_jpeg(self):
        brief = self.brief()
        output = Path(self.temp.name) / "sample.docx"
        write_demo_docx(brief, self.image, output)
        self.assertTrue(output.is_file())
        from docx import Document
        document = Document(output)
        content = "\n".join(p.text for p in document.paragraphs)
        self.assertIn("17", content)
        self.assertIn("مَآل", content)
        self.assertIn("شركة افتراضية", content)
        self.assertIn("لم يُرسل بريد", content)


if __name__ == "__main__":
    unittest.main()
