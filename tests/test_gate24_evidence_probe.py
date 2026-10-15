"""Gate24 screenshot acceptance: entirely mocked sources and local JPEGs."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw

from gate24_evidence_probe import acceptance_probe

NOW = datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)
HAPI = "https://hapijournal.com/feed/"
MASRY = "https://www.almasryalyoum.com/rss/rssfeeds"
TITLE1 = "وزارة التخطيط تناقش التعاون الاقتصادي"
TITLE2 = "وزير التخطيط يعقد لقاءً حول مشروعات جديدة"
URL1 = "https://hapijournal.com/2026/10/15/planning-article-24"
URL2 = "https://www.almasryalyoum.com/news/details/4389999"
DATE = "Thu, 15 Oct 2026 09:00:00 +0000"
CONFIG = json.loads(Path("sources.json").read_text(encoding="utf-8"))


def rss(title, url):
    return (f"<rss><channel><item><title>{title}</title><link>{url}</link>"
            f"<pubDate>{DATE}</pubDate></item></channel></rss>").encode()


def fetch_both(url, limit):
    if url == HAPI:
        return rss(TITLE1, URL1)
    if url == MASRY:
        return rss(TITLE2, URL2)
    raise AssertionError("unexpected feed")


def good_image_capture(url, publisher, destination):
    image = Image.new("RGB", (1200, 900), "white")
    brush = ImageDraw.Draw(image)
    brush.rectangle((0, 0, 1200, 180), fill=(16, 31, 58))
    for y in range(210, 890, 27):
        brush.rectangle((45, y, 1150, y + 12), fill=(20 + y % 35, 43, 54))
    destination.parent.mkdir(exist_ok=True, parents=True)
    image.save(destination, format="JPEG", quality=90)
    return {"ok": True, "actual_url": url,
            "title": TITLE1 if publisher == "hapijournal.com" else TITLE2,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}


class Gate24OriginalScreenshotAcceptanceTests(unittest.TestCase):
    def config(self, root):
        path = Path(root) / "sources.json"
        path.write_text(json.dumps(CONFIG), encoding="utf-8")
        return path

    def test_access_refused_remains_hold_and_audit_redacts_original_url(self):
        with tempfile.TemporaryDirectory() as folder:
            result = acceptance_probe(
                self.config(folder), fetch=fetch_both, clock=NOW,
                capture=lambda *a: {"ok": False, "reason": "publisher_access_refused",
                                     "body": "DO_NOT_LOG_ANY_PAGE_OR_ERROR_URL"},
                max_attempts=1)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["publisher_access_refusals"], 1)
        self.assertEqual(result["verified_screenshots"], 0)
        self.assertEqual(result["failures_by_reason"], {"publisher_access_refused": 1})
        self.assertFalse(result["daily_word_created"])
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["scheduler_enabled"])
        audit = json.dumps(result)
        for private in (URL1, URL2, TITLE1, TITLE2, "DO_NOT_LOG"):
            self.assertNotIn(private, audit)

    def test_good_sample_is_not_treated_as_completed_daily_report(self):
        with tempfile.TemporaryDirectory() as folder:
            result = acceptance_probe(
                self.config(folder), fetch=fetch_both, clock=NOW,
                capture=good_image_capture, max_attempts=2)
        self.assertEqual(result["status"], "SAMPLE_VERIFIED_ONLY")
        self.assertEqual(result["verified_screenshots"], 2)
        self.assertEqual(result["eligible_within_24h"], 2)
        self.assertTrue(all(r["sha256_verified"] for r in result["by_feed"]))
        self.assertFalse(result["all_article_images_verified"])
        self.assertFalse(result["daily_word_created"])
        self.assertNotIn(URL1, json.dumps(result))

    def test_source_outage_never_becomes_full_verified_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            def partial(url, limit):
                if url == MASRY:
                    raise TimeoutError("untrusted-source-url-should-not-leak")
                return fetch_both(url, limit)
            result = acceptance_probe(
                self.config(folder), fetch=partial, clock=NOW,
                capture=good_image_capture)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["coverage"], "DEGRADED")
        self.assertEqual(result["verified_screenshots"], 1)
        self.assertNotIn("untrusted-source-url", json.dumps(result))

    def test_invalid_limits_fail_before_network(self):
        with tempfile.TemporaryDirectory() as folder:
            for count in (-1, 0, 3, True, "1"):
                with self.subTest(count=count), self.assertRaises(ValueError):
                    acceptance_probe(self.config(folder),
                                     fetch=lambda *args: self.fail("network attempted"),
                                     clock=NOW, max_attempts=count)

    def test_zero_matches_is_not_a_success(self):
        with tempfile.TemporaryDirectory() as folder:
            result = acceptance_probe(
                self.config(folder), fetch=lambda url, limit: b"<rss><channel></channel></rss>",
                capture=lambda *a: self.fail("unwanted capture"),
                clock=NOW)
        self.assertEqual(result["status"], "NO_ELIGIBLE_ARTICLES")
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(result["verified_screenshots"], 0)

    def test_unapproved_and_redirected_capture_never_qualifies(self):
        with tempfile.TemporaryDirectory() as folder:
            result = acceptance_probe(
                self.config(folder), fetch=fetch_both, clock=NOW,
                capture=lambda url, publisher, destination: {
                    "ok": True, "actual_url": "https://evil.invalid/not-the-article",
                    "title": TITLE1},
                max_attempts=1)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["by_feed"][0]["reason"], "url_mismatch")


if __name__ == "__main__":
    unittest.main()
