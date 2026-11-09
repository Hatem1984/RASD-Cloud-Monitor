"""Four report preview and trust-boundary regression tests; all synthetic, NO SMTP."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from docx import Document
from PIL import Image

from rasd_four_reports_review import (
    build_four_reports, choose_daily, hourly_window, daily_window,
    validate_item, _states,
)

CUTOFF = datetime(2026, 11, 8, 21, 10, tzinfo=timezone.utc)
# 23:10 Cairo on Nov 8: hourly 22:00-23:00; completed daily is Nov 8 22:00.
DAY = date(2026, 11, 8)


def story(root: Path, channel: str, *, hour: int, number: int) -> dict:
    image = root / f"proof-{channel}-{number}.jpg"
    Image.new("RGB", (450, 600), (247, 240, 224)).save(image, quality=93)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    url = ("https://www.example.com/rasd-news-" + str(number) if channel == "web"
           else "https://www.facebook.com/123/posts/" + str(450 + number))
    return {
        "channel": channel, "platform": "facebook" if channel == "social" else None,
        "source": "ناشر اختبارات مصطنع",
        "title": "عينة اختبار غير حقيقية رقم " + str(number),
        "published_at": datetime(2026, 11, 8, hour, 15,
                                  tzinfo=timezone.utc).isoformat(),
        "url": url, "image_path": str(image), "image_sha256": digest,
        "capture_receipt": {
            "status": "verified", "url": url, "sha256": digest,
            "method": ("approved_web_publisher_capture" if channel == "web"
                       else "authorized_platform_original_capture"),
        },
        "event_label": "حدث مصطنع لا يمثل أخبارًا واقعية",
    }


class FourReportsReviewQA(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cutoff = CUTOFF
        self.items = [
            story(self.root, "web", hour=20, number=101),
            story(self.root, "social", hour=20, number=102),
            story(self.root, "web", hour=18, number=103),
            story(self.root, "social", hour=18, number=104),
        ]
        self.health = [
            {"channel": "web", "name": "الويب التجريبي", "status": "ok"},
            {"channel": "web", "name": "مصدر متعذر", "status": "unavailable"},
            {"channel": "social", "name": "فيسبوك التجريبي", "status": "ok"},
            {"channel": "social", "name": "X غير معتمد", "status": "unauthorized"},
        ]

    def _validated(self):
        return [validate_item(
            x, x["channel"], self.root, {"www.example.com"},
            cutoff=CUTOFF) for x in self.items]

    def test_four_distinct_word_documents_and_dailies_only_accepted(self):
        valid = self._validated()
        accepted = []
        # Only older 18:15 UTC records were previously accepted.
        for row in valid[2:]:
            accepted.append({
                "item_id": row["id"], "image_sha256": row["image_sha256"],
                "status": "smtp_accepted",
                "message_id": "<rasd-" + ("a" * 24) + "@gmail.com>",
                "accepted_at": "2026-11-08T19:00:00+00:00",
            })
        output = self.root / "out"
        summary = build_four_reports(
            self.items, self.health, accepted, cutoff=CUTOFF, date_cairo=DAY,
            evidence_root=self.root, output=output,
            allowed_web_hosts={"www.example.com"})
        self.assertEqual(set(summary["reports"]), {
            "web-hourly", "social-hourly", "web-daily", "social-daily"})
        self.assertFalse(summary["smtp_sent"])
        self.assertFalse(summary["scheduler_changed"])
        self.assertEqual(len(list(output.glob("*.docx"))), 4)
        for key, meta in summary["reports"].items():
            self.assertEqual(meta["items"], 1, key)
            doc = Document(meta["path"])
            self.assertEqual(len(doc.inline_shapes), 1)
            self.assertIn("نسخة مراجعة", "\n".join(p.text for p in doc.paragraphs))
            self.assertNotIn("مآل", "\n".join(p.text for p in doc.paragraphs))
            self.assertIn("تغطية جزئية", "\n".join(p.text for p in doc.paragraphs))
        self.assertTrue(summary["reports"]["web-hourly"]["path"].endswith(
            "RASD-Web-Hourly-REVIEW-NOT-SENT.docx"))
        self.assertEqual(len(list(output.glob("*.json"))), 1)

    def test_no_accepted_daily_does_not_reuse_hourly_items(self):
        summary = build_four_reports(
            self.items, self.health, [], cutoff=CUTOFF, date_cairo=DAY,
            evidence_root=self.root, output=self.root / "zero",
            allowed_web_hosts={"www.example.com"})
        self.assertEqual(summary["reports"]["web-daily"]["items"], 0)
        self.assertEqual(summary["reports"]["social-daily"]["items"], 0)
        self.assertEqual(summary["reports"]["web-hourly"]["items"], 1)
        self.assertEqual(summary["reports"]["social-hourly"]["items"], 1)

    def test_proof_integrity_and_platform_identity_fail_closed(self):
        sample = self.items[1]
        cases = [
            {**sample, "capture_receipt": {"status": "verified",
                "url": sample["url"], "sha256": sample["image_sha256"],
                "method": "operator_manual_screenshot"}},
            {**sample, "url": "https://fakefacebook.example.com/123/posts/452"},
            {**sample, "image_sha256": "f" * 64},
            {**sample, "published_at": "2026-11-09T13:00:00+00:00"},
        ]
        for bad in cases:
            with self.subTest(bad=bad.get("url")):
                with self.assertRaises((ValueError, FileNotFoundError)):
                    validate_item(bad, "social", self.root, {"www.example.com"},
                                  cutoff=CUTOFF)

    def test_day_requires_valid_smtp_archive_identity_and_matched_sha(self):
        item = self._validated()[2]
        start, end = daily_window(DAY)
        with self.assertRaisesRegex(ValueError, "delivery_receipt_identity_hold"):
            choose_daily([item], [{"status": "smtp_accepted",
                "item_id": item["id"], "accepted_at": CUTOFF.isoformat(),
                "message_id": "<fake@anywhere>"}], start, end)
        with self.assertRaisesRegex(ValueError, "daily_original_image_mismatch_hold"):
            choose_daily([item], [{"status": "smtp_accepted",
                "item_id": item["id"], "accepted_at": "2026-11-08T19:00:00+00:00",
                "message_id": "<rasd-" + "b"*24 + "@gmail.com>",
                "image_sha256": "b"*64}], start, end)

    def test_dst_and_partial_status_not_false_zero(self):
        self.assertEqual(len(_states(self.health[:2], "web")), 2)
        self.assertEqual(sum(row["status"] != "ok" for row in self.health), 2)
        start, end = hourly_window(datetime(2026, 11, 8, 21, 10,
                                            tzinfo=timezone.utc))
        self.assertEqual(end-start, timedelta(hours=1))
        summer_start, summer_end = daily_window(date(2026, 7, 5))
        self.assertEqual((summer_end - summer_start).total_seconds(), 86400)
        self.assertNotEqual(summer_end.utcoffset(), None)


if __name__ == "__main__":
    unittest.main()
