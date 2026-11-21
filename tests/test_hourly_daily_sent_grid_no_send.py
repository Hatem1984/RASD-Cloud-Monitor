"""Regression: real hourly Ministry table cards survive SENT-archive daily rollup.

All images, articles and SMTP messages are synthetic in memory. No network,
production credentials, actual email, private CAS or persistent archive.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw
from docx import Document

from daily_report import render_docx
from daily_sent_consolidator import consolidate_sent_words, extract_sent_originals
from monitor import article_id
from cloud_proof_report import word_images_match_capture_digests
from test_daily_sent_consolidation import FakeSent, MergeActualDeliveredWord, SENDER, RECIPIENT


class NewHourlySentGridDailyCompatibility(unittest.TestCase):
    def build_hourly(self, folder: Path, *, count: int = 7):
        articles, ledger_rows, digests = [], [], []
        for index in range(count):
            url = f"https://www.alborsaanews.com/2026/11/20/{10000+index}"
            source = {
                "id": article_id(url),
                "headline": f"وزارة التخطيط — تغطية اقتصادية أصلية وهمية {index+1}",
                "publisher_excerpt": "عينة اختبار محلية بدون اتصال",
                "source": "Alborsa native Egyptian Economy RSS",
                "url": url,
                "published_at_cairo": "2026-11-20 16:30 EET",
                "published_display_cairo": "20 نوفمبر 2026",
            }
            image = folder / f"original-{index}.jpg"
            picture = Image.new("RGB", (1200, 900), (245, 247, 250))
            draw = ImageDraw.Draw(picture)
            draw.rectangle((0, 0, 1199, 195), fill=(10, 30, 76))
            for y in range(220, 860, 25):
                draw.rectangle((50, y, 1100 - 5*index, y+14),
                               fill=((index*27+20) % 210, 70, 100))
            picture.save(image, "JPEG", quality=88)
            articles.append({
                **source, "evidence_image_path": str(image),
                "hourly_publication_bucket": "within_previous_hour"})
            ledger_rows.append(source)
            digests.append({"status": "verified",
                            "sha256": hashlib.sha256(image.read_bytes()).hexdigest()})
        report = {
            "title": "رصد | تقرير المتابعة الساعية — اختبار دون إرسال",
            "report_period": "interval", "report_kind": "hourly",
            "ministry_media_grid": True, "coverage": "HEALTHY",
            "hourly_in_period": count, "hourly_recovered": 0,
            "display_window_start": "20 نوفمبر 2026 16:00 القاهرة",
            "display_window_end": "20 نوفمبر 2026 17:00 القاهرة",
            "articles": articles, "verified_links": count,
            "sources": [{"feed_id": "alborsa", "status": "ok",
                         "verified_links": count}],
            "limitations": "صور أصلية وهمية لا تستخدم للإنتاج",
        }
        doc = folder / "RASD-News-With-Original-Screenshots.docx"
        render_docx(report, doc)
        self.assertEqual(len(Document(doc).inline_shapes), count)
        self.assertTrue(word_images_match_capture_digests(doc, digests))
        return doc.read_bytes(), ledger_rows, digests

    def test_seven_hourly_jpegs_are_extracted_inside_correct_publisher_cards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources, digests = self.build_hourly(root)
            output = root / "extract"
            output.mkdir()
            collected = extract_sent_originals(raw, sources, output)
            self.assertEqual(len(collected), 7)
            self.assertEqual([x[2] for x in collected],
                             [x["sha256"] for x in digests])
            self.assertTrue(all(Path(x[1]).read_bytes().startswith(b"\xff\xd8")
                                for x in collected))

    def test_new_hourly_sent_mime_consolidates_into_original_daily_ministry_word(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources, digests = self.build_hourly(root)
            mailer = MergeActualDeliveredWord()
            message_id = "<rasd-" + "c"*24 + "@gmail.com>"
            imap = FakeSent({message_id: mailer.mail(message_id, raw)})
            state = {"entries": {
                row["id"]: {
                    "kind": "interval_item", "status": "smtp_accepted",
                    "news": row, "message_id": message_id}
                for row in sources
            }}
            word, verified = consolidate_sent_words(
                sources, state, root / "daily",
                sender=SENDER, recipient=RECIPIENT,
                app_password="offline-only",
                start="22:00 أمس", end="22:00 اليوم",
                title="رصد | التقرير المجمع اليومي",
                config={"feeds": [{"id": "alborsa"}]},
                client_factory=lambda: imap,
            )
            final = Document(word)
            self.assertEqual(len(final.inline_shapes), 7)
            self.assertTrue(word_images_match_capture_digests(word, verified))
            self.assertEqual([x["sha256"] for x in verified],
                             [x["sha256"] for x in digests])
            self.assertTrue(imap.selected_readonly)
            self.assertEqual(imap.searched, [message_id])

    def test_verified_gmail_sent_originals_generate_volume_preview_without_smtp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources, digests = self.build_hourly(root, count=7)
            message_id = "<rasd-" + "d"*24 + "@gmail.com>"
            imap = FakeSent({
                message_id: MergeActualDeliveredWord().mail(message_id, raw)})
            state = {"entries": {
                row["id"]: {
                    "kind": "interval_item", "status": "smtp_accepted",
                    "news": row, "message_id": message_id}
                for row in sources
            }}
            volumes, original_proofs = consolidate_sent_words(
                sources, state, root / "preview",
                sender=SENDER, recipient=RECIPIENT,
                app_password="offline-only",
                start="22:00 أمس", end="22:00 اليوم",
                title="رصد | التقرير اليومي — لا إرسال",
                config={"feeds": [{"id": "alborsa"}]},
                client_factory=lambda: imap,
                volume_preflight_only=True)
            self.assertEqual(sum(v["count"] for v in volumes), 7)
            self.assertEqual([i for v in volumes for i in v["article_ids"]],
                             [x["id"] for x in sources])
            self.assertEqual([sha for v in volumes for sha in v["sha256"]],
                             [x["sha256"] for x in digests])
            self.assertEqual(original_proofs, digests)
            self.assertTrue(all(
                word_images_match_capture_digests(
                    volume["path"],
                    original_proofs[sum(v["count"] for v in volumes[:n]):
                                    sum(v["count"] for v in volumes[:n+1])])
                for n, volume in enumerate(volumes)))
            self.assertTrue(imap.selected_readonly)
            self.assertEqual(imap.searched, [message_id])


    def test_title_url_date_or_source_mismatch_never_enters_daily(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw, sources, _ = self.build_hourly(root, count=2)
            output = root / "extract"
            output.mkdir()
            for attribute, altered in (
                ("headline", "خبر آخر ليس هو خبر الناشر"),
                ("url", "https://www.alborsaanews.com/wrong-link"),
                ("published_display_cairo", "تاريخ وهمي مختلف"),
                ("source", "Hapi native news RSS"),
            ):
                with self.subTest(field=attribute):
                    corrupted = [dict(x) for x in sources]
                    corrupted[0][attribute] = altered
                    with self.assertRaisesRegex(RuntimeError,
                                                "daily_sent_grid_"):
                        extract_sent_originals(raw, corrupted, output)


if __name__ == "__main__":
    unittest.main()
