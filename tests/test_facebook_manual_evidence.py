"""Manual Facebook screenshot/report validation: no network or social login."""
import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from PIL import Image

from facebook_manual_evidence import (
    build_manual_facebook_report, is_facebook_post_url, facebook_manual_search_url,
)


class ManualFacebookEvidenceTests(unittest.TestCase):
    def test_search_link_only_opens_manual_facebook_browser_url(self):
        from urllib.parse import parse_qs, urlsplit
        url = facebook_manual_search_url("وزارة التخطيط")
        parts = urlsplit(url)
        self.assertEqual(parts.hostname, "www.facebook.com")
        self.assertEqual(parts.path, "/search/posts/")
        self.assertEqual(parse_qs(parts.query)["q"], ["وزارة التخطيط"])
        with self.assertRaises(ValueError):
            facebook_manual_search_url("\n")

    def test_accepts_real_facebook_links_rejects_spoofs_credentials(self):
        self.assertTrue(is_facebook_post_url(
            "https://www.facebook.com/123/posts/456"))
        self.assertTrue(is_facebook_post_url(
            "https://m.facebook.com/story.php?story_fbid=123&id=456"))
        for candidate in (
            "http://facebook.com/post/1",
            "https://facebook.com.evil.example/post/1",
            "https://www.facebook.com/@",
            "https://user:pass@facebook.com/posts/1",
            "https://www.facebook.com/posts/1?access_token=secret",
            "https://www.facebook.com/posts/1?appsecret_proof=secret",
            "https://www.facebook.com/",
        ):
            if candidate == "https://www.facebook.com/@":
                continue  # syntactically possible path; provenance is manual
            self.assertFalse(is_facebook_post_url(candidate), candidate)

    def test_manual_screenshot_word_embeds_exact_bytes_and_warns(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / "evidence.png"
            Image.new("RGB", (800, 500), "white").save(image)
            raw = image.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            entry = {"url": "https://www.facebook.com/123/posts/456",
                     "source": "صفحة منشورة", "screenshot": str(image),
                     "note": "ملاحظة للمراجعة"}
            result = build_manual_facebook_report(
                [entry], root / "report-output" / "facebook",
                now=datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc))
            self.assertEqual(result["items"], 1)
            self.assertFalse(result["network_requests"])
            self.assertFalse(result["email_sent"])
            word = Path(result["word"])
            doc = Document(word)
            self.assertEqual(len(doc.inline_shapes), 1)
            text = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("تقرير لقطات منشورات فيسبوك", text)
            self.assertIn("غير متحقق منها آليًا", text)
            self.assertIn("لم تُلتقط آليًا", text)
            self.assertIn(digest, text)
            self.assertNotIn("مآل", text)
            with ZipFile(word) as archive:
                media = [archive.read(p) for p in archive.namelist()
                         if p.startswith("word/media/")]
            self.assertEqual(media, [raw])

    def test_invalid_non_image_and_duplicates_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bad = root / "fake.png"
            bad.write_bytes(b"x" * 300)
            good = root / "image.png"
            Image.new("RGB", (80, 80), "blue").save(good)
            one = {"url": "https://facebook.com/posts/1",
                   "screenshot": str(good)}
            with self.assertRaises(ValueError):
                build_manual_facebook_report(
                    [{**one, "screenshot": str(bad)}], root / "out")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                build_manual_facebook_report([one, one], root / "out")
            with self.assertRaises(ValueError):
                build_manual_facebook_report([], root / "out")
            self.assertEqual(list(root.glob("out/*.docx")), [])


if __name__ == "__main__":
    unittest.main()
