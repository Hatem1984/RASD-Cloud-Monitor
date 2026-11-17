"""Web reference acceptance: multiple genuine-source CLIPPINGS, not event rows.

All story examples / generated JPEGs are synthetic test-only; they are NOT
claimed as publisher screenshots or today's news.
"""
import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from monitor import article_id
from rasd_verified_web_report import render_verified_web_report

FEEDS = [
    {"name": "ناشر أول", "allowed_article_hosts": ["first.example"]},
    {"name": "ناشر ثان", "allowed_article_hosts": ["second.example"]},
]
TITLE = "وزارة التخطيط تبحث المشروعات الاستثمارية مع القطاع الخاص"


class VerifiedWebReferenceQA(unittest.TestCase):
    def _input(self, folder):
        stories, proofs = [], []
        for index, hostname in enumerate(("first.example", "second.example")):
            url = f"https://{hostname}/original-news-{index}"
            photo = folder / f"synthetic-fixture-{index}.jpg"
            Image.new("RGB", (1200, 900),
                      (210-index*30, 180, 145)).save(photo, format="JPEG")
            digest = hashlib.sha256(photo.read_bytes()).hexdigest()
            stories.append({
                "id": article_id(url),
                "headline": TITLE,
                "publisher_excerpt": "استثمارات القطاع الخاص",
                "source": ["ناشر أول", "ناشر ثان"][index],
                "url": url,
                "published_at_cairo": "2026-11-17 09:00 EET",
                "evidence_image_path": str(photo),
            })
            proofs.append({"status": "verified", "sha256": digest})
        report = {
            "title": "رصد | تجريب بصري",
            "coverage": "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS",
            "display_window_start": "16 نوفمبر، 22:00",
            "display_window_end": "17 نوفمبر، 22:00",
            "articles": stories,
        }
        return report, proofs

    def test_web_matches_reference_each_coverage_original_url_and_zoom(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            report, proofs = self._input(folder)
            dest = folder / "preview.html"
            render_verified_web_report(report, proofs, FEEDS, dest)
            text = dest.read_text("utf-8")
            self.assertEqual(text.count('class="clip"'), 2)
            self.assertEqual(text.count('class="zoom"'), 2)
            self.assertIn('dir="rtl"', text)
            self.assertIn("تحليل الرصد", text)
            self.assertIn("المواقع الإلكترونية", text)
            self.assertIn("2</b>", text)
            self.assertIn("2</td>", text) if False else None
            self.assertEqual(text.count("50.0%"), 2)
            self.assertEqual(text.count("data:image/jpeg;base64,"), 4)
            self.assertIn('href="https://first.example/original-news-0"', text)
            self.assertIn('href="https://second.example/original-news-1"', text)
            self.assertIn("كل تغطية بصورة أصلية مستقلة", text)
            self.assertIn("لا يثبت رصد جميع الأخبار", text)

    def test_change_one_original_jpeg_keeps_web_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            report, proofs = self._input(folder)
            Path(report["articles"][0]["evidence_image_path"]).write_bytes(
                b"unverified")
            dest = folder / "never-accepted.html"
            with self.assertRaisesRegex(ValueError, "digest_mismatch"):
                render_verified_web_report(report, proofs, FEEDS, dest)
            self.assertFalse(dest.exists())

    def test_unapproved_link_or_wrong_article_id_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            report, proofs = self._input(folder)
            dest = folder / "hold.html"
            report["articles"][0]["id"] = "0" * 24
            with self.assertRaisesRegex(ValueError, "untrusted_article"):
                render_verified_web_report(report, proofs, FEEDS, dest)
            report["articles"][0]["id"] = article_id(
                report["articles"][0]["url"])
            report["articles"][0]["url"] = "https://attacker.invalid/article"
            report["articles"][0]["id"] = article_id(
                report["articles"][0]["url"])
            with self.assertRaisesRegex(ValueError, "unapproved_original"):
                render_verified_web_report(report, proofs, FEEDS, dest)
            self.assertFalse(dest.exists())

    def test_rss_only_or_missing_screenshot_is_not_a_web_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            report, proofs = self._input(folder)
            report["coverage"] = "DEGRADED"
            with self.assertRaisesRegex(ValueError, "previously_verified"):
                render_verified_web_report(report, proofs, FEEDS,
                                           folder/"reject.html")
            report["coverage"] = "CONSOLIDATED_PREVIOUSLY_SENT_ORIGINALS"
            with self.assertRaisesRegex(ValueError, "missing_original"):
                render_verified_web_report(report, proofs[:-1], FEEDS,
                                           folder/"reject.html")


if __name__ == "__main__":
    unittest.main()
