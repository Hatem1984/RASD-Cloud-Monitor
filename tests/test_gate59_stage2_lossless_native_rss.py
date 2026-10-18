"""Gate59: a genuine unified Word must not silently skip broken RSS items.

All payloads/images are synthetic. The normal headline-only preview retains
its historic filtering behavior; only the complete Stage2 Word is stricter.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from monitor import inspect, parse_rss
from unified_ministry_word import build_unified_word

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)
DAY = date(2026, 10, 17)
HAPI = "https://hapijournal.com/news/rasd-qa"
ALMASRY = "https://www.almasryalyoum.com/news/details/99911"
STAMP = "Sat, 17 Oct 2026 11:00:00 +0300"


def item(title="وزارة التخطيط", url=HAPI, published=STAMP):
    return ("<item><title>" + escape(title) + "</title><link>" +
            escape(url) + "</link><pubDate>" + escape(published) +
            "</pubDate></item>")


def rss(*items):
    return ("<rss><channel>" + "".join(items) + "</channel></rss>").encode("utf-8")


class PreviousOfficialDay:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def discover_page(self, page):
        if page == 1:
            return ["https://mped.gov.eg/singlenews?id=7267&lang=ar"]
        return []

    def inspect(self, url, *, keywords, target_day, image):
        return {"status": "OUT_OF_WINDOW", "published_date_cairo": "2026-10-16"}


class CompleteNativeRSSInventoryTests(unittest.TestCase):
    def test_complete_publisher_items_pass_without_changing_headline_filter(self):
        data = rss(item(title="البورصة"), item(title="وزير التخطيط", url=HAPI+"2"))
        valid, found = parse_rss(data, CONFIG["feeds"][0], CONFIG["keywords"],
                                 now=NOW, require_complete_items=True)
        self.assertEqual(valid, 2)
        self.assertEqual(len(found), 1)
        self.assertIn("وزير التخطيط", found[0]["headline"])

    def test_valid_empty_channel_can_still_be_healthy(self):
        valid, found = parse_rss(rss(), CONFIG["feeds"][0],
                                 CONFIG["keywords"], now=NOW,
                                 require_complete_items=True)
        self.assertEqual((valid, found), (0, []))

    def test_structurally_missing_channel_never_counts_as_healthy_full_report(self):
        with self.assertRaisesRegex(ValueError, "rss_channel_unverifiable"):
            parse_rss(b"<rss></rss>", CONFIG["feeds"][0],
                      CONFIG["keywords"], now=NOW, require_complete_items=True)

    def test_invalid_unrelated_item_blocks_instead_of_silently_dropping(self):
        bad = [
            "<item><title>خبر اقتصادي</title><link></link><pubDate>" +
                STAMP + "</pubDate></item>",
            "<item><title></title><link>" + HAPI +
                "</link><pubDate>" + STAMP + "</pubDate></item>",
            item("خبر اقتصادي", "https://example.org/stolen"),
            item("خبر اقتصادي", "http://hapijournal.com/no-tls"),
            item("خبر اقتصادي", "https://hapijournal.com:444/not-approved"),
            item("خبر اقتصادي", "https://hapijournal.com/a", ""),
            item("خبر اقتصادي", "https://hapijournal.com/a", "not-a-time"),
            item("خبر اقتصادي", "https://hapijournal.com/a",
                 "Sat, 17 Oct 2026 11:00:00"),
        ]
        for broken in bad:
            with self.subTest(broken=broken[:40]):
                content = rss(item(), broken)
                # The original read-only public preview remains backwards
                # compatible; it must NEVER widen the saved four phrases.
                preview_count, preview_matches = parse_rss(
                    content, CONFIG["feeds"][0], CONFIG["keywords"], now=NOW,
                )
                self.assertEqual(preview_count, 1)
                self.assertEqual(len(preview_matches), 1)
                with self.assertRaisesRegex(
                    ValueError, "rss_original_item_(identity|date)_unverifiable"
                ):
                    parse_rss(content, CONFIG["feeds"][0], CONFIG["keywords"],
                              now=NOW, require_complete_items=True)

    def test_conflicting_same_publisher_url_title_or_original_date_holds(self):
        for conflict in (
            item("الوزارة تنظم اجتماعًا", HAPI),
            item("وزارة التخطيط", HAPI, "Sat, 17 Oct 2026 12:00:00 +0300"),
        ):
            with self.subTest(conflict=conflict[:65]):
                with self.assertRaisesRegex(ValueError, "rss_original_duplicate_conflict"):
                    parse_rss(rss(item(), conflict), CONFIG["feeds"][0],
                              CONFIG["keywords"], now=NOW,
                              require_complete_items=True)

    def test_exact_duplicate_is_allowed_and_only_matched_once(self):
        valid, found = parse_rss(rss(item(), item()), CONFIG["feeds"][0],
                                 CONFIG["keywords"], now=NOW,
                                 require_complete_items=True)
        self.assertEqual(valid, 2)
        self.assertEqual(len(found), 1)

    def test_inspect_fail_closed_only_when_explicitly_requested(self):
        broken = rss(item(), item("other", "https://example.org/foreign"))
        def fetch(url, limit):
            return broken if url == CONFIG["feeds"][0]["url"] else rss()
        old = inspect(CONFIG, fetch=fetch, now=NOW)
        self.assertEqual(old["sources"][0]["status"], "ok")
        strict = inspect(CONFIG, fetch=fetch, now=NOW,
                         require_complete_items=True, article_limit=200)
        self.assertEqual(strict["sources"][0]["status"], "failed")
        self.assertEqual(strict["sources"][0]["error"], "ValueError")
        self.assertEqual(strict["sources"][1]["status"], "ok")
        self.assertEqual(strict["planning_headline_matches"], 0)

    def test_unified_word_incomplete_mandatory_rss_holds_without_word(self):
        broken = rss(item(), item("other", "https://example.org/foreign"))
        def fetch(url, limit):
            return broken if url == CONFIG["feeds"][0]["url"] else rss()
        with tempfile.TemporaryDirectory() as folder:
            src = Path(folder) / "sources.json"
            src.write_text(json.dumps(CONFIG, ensure_ascii=False), encoding="utf-8")
            target = Path(folder) / "private-report"
            evidence = build_unified_word(
                src, target, target_day=DAY, now=NOW, fetch=fetch,
                official_driver_factory=PreviousOfficialDay,
            )
            self.assertEqual(evidence["status"], "HOLD")
            self.assertFalse(evidence["all_sources_healthy"])
            self.assertFalse(evidence["word_created"])
            self.assertEqual(evidence["source_health"][0]["status"], "failed")
            self.assertEqual(evidence["source_health"][1]["status"], "ok")
            self.assertFalse(list(target.glob("RASD-Unified-*.docx")))

    def test_production_keywords_and_exact_approved_feeds_unchanged(self):
        self.assertEqual(CONFIG["keywords"], [
            "وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
            "التخطيط والتنمية الاقتصادية",
        ])
        self.assertEqual([x["url"] for x in CONFIG["feeds"]], [
            "https://hapijournal.com/feed/",
            "https://www.almasryalyoum.com/rss/rssfeeds",
        ])


if __name__ == "__main__":
    unittest.main()
