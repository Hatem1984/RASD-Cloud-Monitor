"""Gate 23 — precise Cairo pilot previews, no secrets/SMTP/network."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from docx import Document
from daily_report import gather, generate

CAIRO = ZoneInfo("Africa/Cairo")
NOW = datetime(2026, 10, 15, 11, 57, tzinfo=CAIRO)
START = datetime(2026, 10, 15, 8, 0, tzinfo=CAIRO)
CONFIG = json.loads(Path("sources.json").read_text(encoding="utf-8"))
HAPI = "https://hapijournal.com/feed/"
MASRY = "https://www.almasryalyoum.com/rss/rssfeeds"


def rss(rows):
    import xml.sax.saxutils as sx
    return ("<rss><channel>" + "".join(
        "<item><title>" + sx.escape(title) + "</title><link>" + sx.escape(url) +
        "</link><pubDate>" + format_datetime(date) + "</pubDate></item>"
        for title, url, date in rows
    ) + "</channel></rss>").encode("utf-8")


def some_articles(url, limit):
    if url == HAPI:
        rows = [
            ("وزارة التخطيط — خبر قبل الثامنة",
             "https://hapijournal.com/planning-before-eight",
             START - timedelta(minutes=1)),
        ]
        rows += [
            (f"وزارة التخطيط — تقرير {i}",
             f"https://hapijournal.com/planning-pilot-{i}",
             START + timedelta(minutes=5 * i))
            for i in range(1, 23)
        ]
        return rss(rows)
    if url == MASRY:
        return rss([
            ("وزير التخطيط يعقد اجتماعاً",
             "https://www.almasryalyoum.com/news/details/9234567",
             START),
        ])
    raise AssertionError("unapproved mocked feed")


class Gate23CairoPilotTests(unittest.TestCase):
    def test_exact_cairo_0800_boundary_and_safe_20_cap(self):
        report = gather(CONFIG, fetch=some_articles, now=NOW,
                        start_cairo=START, max_articles=20)
        self.assertEqual(report["window_start_cairo"], "2026-10-15 08:00 EEST")
        self.assertEqual(report["window_article_count"], 23)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["article_limit"], 20)
        self.assertEqual(len(report["articles"]), 20)
        self.assertEqual(report["articles"][0]["headline"], "وزارة التخطيط — تقرير 22")
        self.assertTrue(all("before-eight" not in x["url"] for x in report["articles"]))
        self.assertEqual(report["articles"][-1]["headline"], "وزارة التخطيط — تقرير 3")
        self.assertEqual(report["coverage"], "HEALTHY")
        self.assertFalse(report["email_sent"])
        self.assertFalse(report["scheduler_enabled"])

    def test_exact_0800_article_included_when_below_cap(self):
        report = gather(CONFIG, fetch=some_articles, now=NOW,
                        start_cairo=START, max_articles=20)
        self.assertEqual(report["window_article_count"], 23)
        report2 = gather(CONFIG, fetch=lambda url, limit: (
            rss([("وزير التخطيط عند الثامنة",
                  "https://hapijournal.com/planning-at-eight", START)])
            if url == HAPI else rss([])),
            now=NOW, start_cairo=START, max_articles=20)
        self.assertEqual(len(report2["articles"]), 1)
        self.assertEqual(report2["articles"][0]["headline"], "وزير التخطيط عند الثامنة")

    def test_production_default_still_caps_at_fifteen(self):
        report = gather(CONFIG, fetch=some_articles, now=NOW)
        self.assertEqual(report["article_limit"], 15)
        self.assertEqual(len(report["articles"]), 15)
        self.assertEqual(report["window_article_count"], 24)

    def test_rejects_invalid_and_future_cross_date_windows(self):
        invalid = [
            START.replace(tzinfo=None),
            START - timedelta(days=1),
            NOW + timedelta(minutes=2),
            NOW - timedelta(hours=25),
        ]
        for timestamp in invalid:
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                gather(CONFIG, fetch=some_articles, now=NOW, start_cairo=timestamp)
        for limit in (0, 21, True, 1.5, "20"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                gather(CONFIG, fetch=some_articles, now=NOW, max_articles=limit)

    def test_preview_word_explicitly_discloses_images_and_event_count_unverified(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cfg = root / "sources.json"
            cfg.write_text(json.dumps(CONFIG, ensure_ascii=False), encoding="utf-8")
            result = generate(cfg, root / "out", fetch=some_articles,
                              now=NOW, start_cairo=START, max_articles=20)
            self.assertTrue(result["preview_only"])
            self.assertEqual(result["articles"], 20)
            self.assertEqual(result["window_article_count"], 23)
            self.assertTrue(result["truncated"])
            self.assertIsNone(result["events_verified"])
            self.assertEqual(result["publisher_screenshots_verified"], 0)
            self.assertFalse(result["email_sent"])
            self.assertFalse(result["scheduler_enabled"])
            files = list((root / "out").glob("*.docx"))
            self.assertEqual(len(files), 1)
            doc = Document(files[0])
            all_text = " ".join(p.text for p in doc.paragraphs)
            self.assertIn("مسودة", all_text)
            self.assertIn("غير محددة آليًا", all_text)
            self.assertIn("لا تحتوي صورًا موثقة", all_text)
            self.assertEqual(len(doc.inline_shapes), 0)


if __name__ == "__main__":
    unittest.main()
