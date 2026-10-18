"""Gate 27: final report media-to-capture SHA-256 integrity (offline only).

No real URLs are fetched, no Google/GitHub private credentials, no email or cron.
"""
from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from cloud_proof_report import build_proof_report, word_images_match_capture_digests
from daily_report import render_docx

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
TITLE = "وزارة التخطيط تستعرض مؤشرات التنمية الاقتصادية"
URLS = {
    "hapi": "https://hapijournal.com/gate27-verified-story",
    "masry": "https://www.almasryalyoum.com/news/details/4380001",
}


def fake_fetch(url, size_limit):
    article = URLS["hapi"] if "hapijournal.com" in url else URLS["masry"]
    return (f"<rss><channel><item><title>{TITLE}</title><link>{article}</link>"
            "<pubDate>Thu, 15 Oct 2026 10:00:00 +0000</pubDate>"
            "</item></channel></rss>").encode("utf-8")


def original_jpeg(url, publisher, destination):
    image = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(image)
    color = (12, 46, 87) if "hapijournal" in url else (87, 40, 12)
    draw.rectangle((0, 0, 1199, 180), fill=color)
    for line in range(210, 860, 24):
        draw.rectangle((60, line, 1150, line + 13),
                       fill=(30 + line % 55, 35 + line % 60, 65))
    image.save(destination, quality=91)
    return {"ok": True, "actual_url": url, "title": TITLE,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}


def build(folder, *, capture=original_jpeg):
    return build_proof_report(Path("sources.json"), folder,
                              fetch=fake_fetch, capture=capture, now=NOW)


class Gate27WordImageIntegrityTests(unittest.TestCase):
    def test_two_distinct_original_captures_are_embedded_and_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            outcome = build(folder)
            self.assertEqual(outcome["status"], "READY")
            self.assertEqual(outcome["screenshots_verified"], 2)
            self.assertTrue(outcome["word_created"])
            word = next(folder.glob("RASD-Daily-*.docx"))
            self.assertTrue(word_images_match_capture_digests(word, outcome["entries"]))
            self.assertFalse(outcome["email_sent"])
            self.assertFalse(outcome["scheduler_enabled"])

    def test_mutated_jpeg_digest_fails_closed_before_final_or_private_archive(self):
        class NeverArchive:
            def publish_ready(self, **kwargs):
                raise AssertionError("corrupt evidence cannot reach private archive")

        def corrupt_media(report, word):
            render_docx(report, word)
            with zipfile.ZipFile(word) as archive:
                entries = [(item, archive.read(item.filename))
                           for item in archive.infolist()]
            with zipfile.ZipFile(word, "w") as archive:
                for item, data in entries:
                    if item.filename.startswith("word/media/"):
                        data += b"unaltered-image-claim-is-false"
                    archive.writestr(item, data)

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("cloud_proof_report.render_docx", side_effect=corrupt_media):
                outcome = build_proof_report(
                    Path("sources.json"), folder, fetch=fake_fetch,
                    capture=original_jpeg, now=NOW, archive_writer=NeverArchive())
            self.assertEqual(outcome["status"], "HOLD")
            self.assertEqual(outcome["failure"], "word_evidence_integrity_failed")
            self.assertFalse(outcome["word_created"])
            self.assertFalse(list(folder.glob("*.docx")))

    def test_omitted_picture_in_word_is_not_accepted_by_count_or_receipts(self):
        def omit_one_picture(report, word):
            modified = copy.deepcopy(report)
            modified["articles"][1].pop("evidence_image_path")
            render_docx(modified, word)

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("cloud_proof_report.render_docx", side_effect=omit_one_picture):
                outcome = build(folder)
            self.assertEqual(outcome["status"], "HOLD")
            self.assertFalse(list(folder.glob("*.docx")))

    def test_orphan_unreferenced_picture_in_package_fails_closed(self):
        def add_orphan(report, word):
            render_docx(report, word)
            with zipfile.ZipFile(word, "a") as archive:
                archive.writestr("word/media/orphan.jpg", b"not linked to an article")

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("cloud_proof_report.render_docx", side_effect=add_orphan):
                outcome = build(folder)
            self.assertEqual(outcome["status"], "HOLD")
            self.assertFalse(list(folder.glob("*.docx")))

    def test_swapped_article_screenshots_are_hold_even_with_same_byte_digests(self):
        """Matching the screenshot SET is insufficient: pictures must match articles."""
        def swap_evidence_placements(report, word):
            altered = copy.deepcopy(report)
            rows = altered["articles"]
            self.assertEqual(len(rows), 2)
            rows[0]["evidence_image_path"], rows[1]["evidence_image_path"] = (
                rows[1]["evidence_image_path"], rows[0]["evidence_image_path"]
            )
            render_docx(altered, word)

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch("cloud_proof_report.render_docx",
                       side_effect=swap_evidence_placements):
                outcome = build(folder)
            self.assertEqual(outcome["screenshots_verified"], 2)
            self.assertEqual(outcome["status"], "HOLD")
            self.assertEqual(outcome["failure"], "word_evidence_integrity_failed")
            self.assertFalse(outcome["word_created"])
            self.assertFalse(list(folder.glob("*.docx")))

    def test_failed_same_day_retry_does_not_leave_previous_final_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(build(folder)["status"], "READY")
            self.assertEqual(len(list(folder.glob("*.docx"))), 1)
            blocked = lambda *args: {"ok": False, "reason": "publisher_access_refused"}
            second = build(folder, capture=blocked)
            self.assertEqual(second["status"], "HOLD")
            self.assertFalse(list(folder.glob("RASD-Daily-*.docx")))


if __name__ == "__main__":
    unittest.main()
