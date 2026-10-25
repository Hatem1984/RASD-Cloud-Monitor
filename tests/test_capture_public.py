"""Offline screenshot safety checks; no web browser or news-site calls."""
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from capture_public import (allowed_url, image_quality, capture_publisher,
                            classify_publisher_http_status, accept_staged_image,
                            visible_article_image_missing)
from screenshot_probe import choose_targets, REFERENCE


class BrowserSafetyTests(unittest.TestCase):
    def test_exact_article_hosts(self):
        self.assertTrue(allowed_url("https://www.elwatannews.com/news/details/8375816", "elwatannews.com"))
        self.assertTrue(allowed_url("https://hapijournal.com/story", "hapijournal.com"))
        self.assertFalse(allowed_url("https://media.elwatannews.com/picture.jpg", "elwatannews.com"))

    def test_reject_cross_domain_and_scheme_tricks(self):
        for url in (
            "http://www.elwatannews.com/news/1",
            "https://www.elwatannews.com:9999/news/1",
            "https://www.elwatannews.com.attacker.invalid/",
            "https://attacker.invalid/?host=elwatannews.com",
            "file:///etc/passwd",
            "https://user:pass@www.elwatannews.com/news/1",
            "https://127.0.0.1/internal",
        ):
            with self.subTest(url=url):
                self.assertFalse(allowed_url(url, "elwatannews.com"))

    def test_assets_only_in_publisher_subdomains(self):
        self.assertTrue(allowed_url("https://media.elwatannews.com/images/abc.jpg",
                                    "elwatannews.com", asset=True))
        self.assertFalse(allowed_url("https://media.elwatannews.com.evil.invalid/x",
                                     "elwatannews.com", asset=True))
        self.assertFalse(allowed_url("https://tracker.example/script.js",
                                     "elwatannews.com", asset=True))

    def test_unloaded_article_image_is_fail_closed_without_substituting_media(self):
        self.assertTrue(visible_article_image_missing([
            {"visible": True, "loaded": False}]))
        self.assertFalse(visible_article_image_missing([
            {"visible": False, "loaded": False},
            {"visible": True, "loaded": True}]))
        self.assertFalse(visible_article_image_missing([]))
        self.assertTrue(visible_article_image_missing("untrusted-json"))
        self.assertTrue(visible_article_image_missing([{}]))

    def test_blank_realistic_jpeg_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "empty.jpg"
            Image.new("RGB", (1200, 900), (244, 245, 249)).save(dest)
            result = image_quality(dest)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason"], "blank_or_low_content")

    def test_article_like_jpeg_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "article.jpg"
            photo = Image.new("RGB", (1200, 900), "white")
            draw = ImageDraw.Draw(photo)
            draw.rectangle((0, 0, 1200, 145), fill=(21, 34, 55))
            for y in range(220, 740, 48):
                draw.rectangle((120, y, 1040, y + 14), fill=(45, 48, 54))
            photo.save(dest)
            self.assertTrue(image_quality(dest)["accepted"])

    def test_publisher_hero_uniform_grey_is_held_even_with_heading_and_ads(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "original-publisher-with-unloaded-hero.jpg"
            photo = Image.new("RGB", (1200, 900), "white")
            paint = ImageDraw.Draw(photo)
            paint.rectangle((0, 0, 1200, 140), fill=(18, 40, 68))
            paint.rectangle((70, 195, 710, 240), fill=(25, 28, 34))
            paint.rectangle((810, 160, 1150, 550), fill=(12, 95, 140))
            # Only this protected synthetic defect is grey; publisher ads and
            # heading ensure global screenshot variance would otherwise pass.
            paint.rectangle((45, 355, 780, 745), fill=(247, 247, 247))
            photo.save(path, quality=90)
            result = image_quality(path)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["reason"], "suspicious_flat_original_lead_media")

    def test_genuine_colorful_lead_not_rejected_by_grey_placeholder_guard(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "article-real-photo.jpg"
            photo = Image.new("RGB", (1200, 900), "white")
            paint = ImageDraw.Draw(photo)
            paint.rectangle((0, 0, 1200, 140), fill=(18, 40, 68))
            paint.rectangle((70, 195, 710, 240), fill=(25, 28, 34))
            for x in range(50, 770, 60):
                paint.rectangle((x, 350, x + 55, 745), fill=(
                    (50 + x) % 220, (20 + x // 2) % 220, (130 + x) % 220))
            photo.save(path, quality=90)
            result = image_quality(path)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["reason"], "ok")

    def test_corrupt_and_too_small_images_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "broken.jpg"
            dest.write_bytes(b"not-an-image")
            self.assertEqual(image_quality(dest)["reason"], "invalid_image")
            Image.new("RGB", (2, 2), "white").save(dest)
            self.assertEqual(image_quality(dest)["reason"], "too_small_dimensions")

    def test_without_live_match_regression_is_explicit(self):
        targets = choose_targets({"matched_public_articles": []})
        self.assertEqual(targets[0]["url"], REFERENCE["url"])
        self.assertEqual(targets[0]["selection"],
                         "historic_publisher_reference_not_new_discovery")

    def test_with_real_rss_match_no_historical_fallback(self):
        item = {"url": "https://hapijournal.com/news/1",
                "headline": "وزير التخطيط يعقد اجتماعا"}
        targets = choose_targets({"matched_public_articles": [item]})
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["selection"], "live_feed_discovery")
        self.assertEqual(targets[0]["url"], item["url"])

    def test_unknown_source_cannot_override_trusted_capture(self):
        item = {"url": "https://evil.invalid/news/1",
                "headline": "وزير التخطيط خبر غير معتمد"}
        targets = choose_targets({"matched_public_articles": [item]})
        self.assertEqual(targets, [REFERENCE])

    def test_http_failures_are_fixed_codes_not_untrusted_server_text(self):
        cases = {
            None: "publisher_no_http_response",
            401: "publisher_access_refused",
            403: "publisher_access_refused",
            404: "publisher_article_unavailable",
            410: "publisher_article_unavailable",
            429: "publisher_rate_limited",
            500: "publisher_server_error",
            503: "publisher_server_error",
            418: "publisher_http_failure",
        }
        for status, expected in cases.items():
            with self.subTest(status=status):
                self.assertEqual(classify_publisher_http_status(status), expected)

    def test_staged_valid_image_is_committed_only_after_quality_checks(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            staged, final = folder / "candidate.jpg", folder / "approved.jpg"
            image = Image.new("RGB", (1200, 900), "white")
            paint = ImageDraw.Draw(image)
            paint.rectangle((0, 0, 1200, 180), fill=(18, 30, 52))
            for y in range(210, 850, 32):
                paint.rectangle((40, y, 1110, y + 12), fill=(35, 45, 66))
            image.save(staged, quality=85)
            self.assertGreater(staged.stat().st_size, 8000)
            output = accept_staged_image(staged, final)
            self.assertTrue(output["ok"])
            self.assertTrue(final.is_file())
            self.assertFalse(staged.exists())
            self.assertEqual(output["image"], "approved.jpg")

    def test_rejected_staged_image_does_not_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            staged, final = folder / "candidate.jpg", folder / "approved.jpg"
            final.write_bytes(b"previous-accepted-evidence")
            old_bytes = final.read_bytes()
            staged.write_bytes(b"invalid-jpeg" * 2000)
            output = accept_staged_image(staged, final)
            self.assertFalse(output["ok"])
            self.assertEqual(output["reason"], "visual_qa_invalid_image")
            self.assertEqual(final.read_bytes(), old_bytes)

    def test_bad_publisher_denied_before_playwright(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "bad.jpg"
            result = capture_publisher("https://evil.invalid/test",
                                       "elwatannews.com", dest)
            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "publisher_not_approved")
            self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
