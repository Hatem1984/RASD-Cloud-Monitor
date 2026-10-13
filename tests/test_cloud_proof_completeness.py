"""Offline tests for strict screenshot-to-report completeness."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw
from docx import Document
from cloud_proof_report import build_proof_report

NOW = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
TITLE = "وزارة التخطيط تستعرض مؤشرات التنمية الاقتصادية"


def fetch(url, limit):
    article = ("https://hapijournal.com/story" if "hapijournal" in url else
               "https://www.almasryalyoum.com/news/details/4380989")
    return (f"<rss><channel><item><title>{TITLE}</title><link>{article}</link>"
            "<pubDate>Tue, 13 Oct 2026 11:00:00 +0000</pubDate></item></channel></rss>").encode()


def capture(url, publisher, destination):
    image = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 1199, 200), fill=(10, 20, 40))
    for y in range(220, 880, 25):
        draw.rectangle((30, y, 1150, y+15), fill=(30, 40, 50))
    image.save(destination, quality=90)
    return {"ok": True, "actual_url": url, "title": TITLE}


class CloudReportProofTests(unittest.TestCase):
    def test_all_verified_publisher_images_embedded_in_final_word_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = build_proof_report(Path("sources.json"), Path(tmp),
                                        fetch=fetch, capture=capture, now=NOW)
            self.assertEqual(report["status"], "READY")
            self.assertEqual(report["screenshots_verified"], 2)
            self.assertTrue(report["word_created"])
            self.assertEqual(report["owner_pc_required"], False)
            words = list(Path(tmp).glob("RASD-Daily-*.docx"))
            self.assertEqual(len(words), 1)
            doc = Document(words[0])
            self.assertEqual(len(doc.inline_shapes), 2)
            self.assertFalse(list(Path(tmp).glob("*.pdf")))

    def test_degraded_source_coverage_holds_final_report(self):
        def one_feed(url, limit):
            if "almasryalyoum" in url:
                raise TimeoutError("offline simulated publisher feed outage")
            return fetch(url, limit)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            result = build_proof_report(Path("sources.json"), output,
                                        fetch=one_feed, capture=capture, now=NOW)
            self.assertEqual(result["coverage"], "DEGRADED")
            self.assertEqual(result["screenshots_missing"], 0)
            self.assertEqual(result["status"], "HOLD")
            self.assertFalse(list(output.glob("*.pdf")))

    def test_blocked_one_holds_all_final_documents(self):
        def selective(url, publisher, dest):
            if "almasryalyoum" in url:
                return {"ok": False, "reason": "publisher_access_refused"}
            return capture(url, publisher, dest)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            report = build_proof_report(Path("sources.json"), output,
                                        fetch=fetch, capture=selective, now=NOW)
            self.assertEqual(report["status"], "HOLD")
            self.assertEqual(report["screenshots_missing"], 1)
            self.assertFalse(list(output.glob("*.pdf")))
            self.assertFalse(list(output.glob("*.docx")))
            self.assertEqual(json.loads(next(output.glob("*manifest.json")).read_text())["status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
