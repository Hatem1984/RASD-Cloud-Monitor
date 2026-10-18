"""Gate36 exact-date 25-article QA: synthetic publisher fixtures, no real network."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw

from gate36_yesterday_25_qa import run_qa, TARGET_COUNT, TARGET_DAY
from daily_report import MAX_ARTICLES, MAX_PREVIEW_ARTICLES

CAIRO = ZoneInfo("Africa/Cairo")
NOW = datetime(2026, 10, 18, 10, 30, tzinfo=CAIRO)
CONFIG = json.loads(Path("sources.json").read_text(encoding="utf-8"))
URLS = {}


def make_rows(total=25, *, include_neighbor=False):
    global URLS
    URLS = {}
    rows = {"hapi": [], "almasryalyoum": []}
    for i in range(total):
        feed = "hapi" if i % 2 == 0 else "almasryalyoum"
        url = (f"https://hapijournal.com/2026/10/17/planning-qa-{i}"
               if feed == "hapi" else
               f"https://www.almasryalyoum.com/news/details/{8800000+i}")
        title = f"وزارة التخطيط تناقش مؤشرات اقتصادية رقم {i}"
        stamp = datetime(2026, 10, 17, 0, 0, tzinfo=CAIRO) + timedelta(minutes=i*53)
        rows[feed].append((title, url, stamp))
        URLS[url] = title
    if include_neighbor:
        for d, key in ((datetime(2026, 10, 16, 23, 59, tzinfo=CAIRO), "early"),
                       (datetime(2026, 10, 18, 0, 0, tzinfo=CAIRO), "late")):
            url = f"https://hapijournal.com/qa-excluded-{key}"
            title = "وزارة التخطيط خارج يوم الاختبار"
            rows["hapi"].append((title, url, d))
            URLS[url] = title
    return rows


def fetch_factory(rows, *, fail_source=None):
    def fetch(url, limit):
        feed = "hapi" if url == "https://hapijournal.com/feed/" else "almasryalyoum"
        if fail_source == feed:
            raise TimeoutError("simulated_no_live_feed")
        items = "".join(
            f"<item><title>{escape(title)}</title><link>{escape(link)}</link>"
            f"<pubDate>{format_datetime(stamp)}</pubDate></item>"
            for title, link, stamp in rows[feed]
        )
        return f"<rss><channel>{items}</channel></rss>".encode("utf-8")
    return fetch


def synthetic_capture(url, publisher, destination):
    # Draw varied high-contrast synthetic test fixtures; never actual pages.
    from hashlib import sha256
    pixels = sha256(url.encode("utf-8")).digest()
    img = Image.new("RGB", (1200, 900), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1199, 200), fill=(10+pixels[0] % 70, 32, 85))
    for y in range(220, 870, 27):
        draw.rectangle((35, y, 1150, y + 16),
                       fill=(30 + y % 50, 44 + pixels[1] % 20, 65))
    # Each synthetic article gets distinct original-publisher fixture bytes.
    # Accidental image deduplication would correctly fail strict DOCX checks.
    for n, value in enumerate(pixels):
        x = 50 + 33 * n
        draw.rectangle((x, 770, x + 22, 780 + value // 2),
                       fill=(value, 30 + n * 3, 160))
    img.save(destination, quality=90)
    return {"ok": True, "actual_url": url, "title": URLS[url]}


class PreviousCairoDay25AcceptanceTests(unittest.TestCase):
    def execute(self, total=25, *, fail_source=None,
                bad_image=False, include_neighbor=False):
        rows = make_rows(total, include_neighbor=include_neighbor)
        def capture(url, publisher, destination):
            if bad_image and "/news/details/" in url:
                return {"ok": False, "reason": "publisher_access_refused"}
            return synthetic_capture(url, publisher, destination)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sources.json"
            path.write_text(json.dumps(CONFIG), encoding="utf-8")
            result = run_qa(config_path=path, fetch=fetch_factory(
                rows, fail_source=fail_source), capture=capture, now=NOW)
            self.assertFalse(list(Path(temp).glob("*.docx")))
            return result

    def test_full_25_valid_original_page_qa_images_pass_only_in_isolated_mode(self):
        result = self.execute(25, include_neighbor=True)
        self.assertEqual(result["status"], "READY_QA_ONLY")
        self.assertEqual(result["eligible_articles_on_target_date"], 25)
        self.assertEqual(result["verified_original_page_images"], 25)
        self.assertTrue(result["word_bytes_verified_in_ephemeral_runner"])
        self.assertEqual(result["target_date_cairo"], "2026-10-17")
        self.assertEqual(result["window_start_cairo"][:10], "2026-10-17")
        self.assertEqual(result["window_end_exclusive_cairo"][:10], "2026-10-18")
        self.assertFalse(result["final_report_published"])
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["public_document_or_images_uploaded"])
        self.assertFalse(result["scheduler_enabled"])
        # The actual, approved production and preview limits remain untouched.
        self.assertEqual(MAX_ARTICLES, 15)
        self.assertEqual(MAX_PREVIEW_ARTICLES, 20)

    def test_24_available_does_not_fabricate_the_25th(self):
        result = self.execute(24)
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["eligible_articles_on_target_date"], 24)
        self.assertEqual(result["verified_original_page_images"], 24)
        self.assertFalse(result["word_bytes_verified_in_ephemeral_runner"])

    def test_more_than_25_selects_only_25_without_overreach(self):
        result = self.execute(26)
        self.assertEqual(result["eligible_articles_on_target_date"], 26)
        self.assertEqual(result["selected_articles"], 25)
        self.assertEqual(result["verified_original_page_images"], 25)
        self.assertEqual(result["status"], "READY_QA_ONLY")

    def test_one_denied_screenshot_holds_entire_report(self):
        result = self.execute(25, bad_image=True)
        self.assertEqual(result["status"], "HOLD")
        self.assertGreater(result["missing_or_rejected_images"], 0)
        self.assertFalse(result["word_bytes_verified_in_ephemeral_runner"])
        self.assertEqual(result["rejection_reasons"].get("publisher_access_refused"),
                         result["missing_or_rejected_images"])

    def test_one_unhealthy_feed_holds_even_if_other_has_stories(self):
        result = self.execute(25, fail_source="hapi")
        self.assertEqual(result["coverage"], "DEGRADED")
        self.assertEqual(result["status"], "HOLD")
        self.assertFalse(result["word_bytes_verified_in_ephemeral_runner"])

    def test_outside_day_or_unapproved_source_is_rejected(self):
        rows = make_rows(25)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "sources.json"
            changed = dict(CONFIG)
            changed["feeds"] = CONFIG["feeds"] + [{
                "id": "unreviewed", "name": "Unreviewed news",
                "url": "https://unreviewed.invalid/rss",
                "allowed_article_hosts": ["unreviewed.invalid"],
            }]
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "approved_source_profile_required"):
                run_qa(config_path=path, fetch=fetch_factory(rows),
                       capture=synthetic_capture, now=NOW)
            path.write_text(json.dumps(CONFIG), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "gate36_must_run_on_day_after_target"):
                run_qa(config_path=path, fetch=fetch_factory(rows),
                       capture=synthetic_capture,
                       now=NOW + timedelta(days=1))
            with self.assertRaisesRegex(ValueError, "gate36_naive_clock_forbidden"):
                run_qa(config_path=path, fetch=fetch_factory(rows),
                       capture=synthetic_capture,
                       now=NOW.replace(tzinfo=None))


if __name__ == "__main__":
    unittest.main()
