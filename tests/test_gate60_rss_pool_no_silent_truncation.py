"""Gate60: Stage2 must not accept 200 of 201 native RSS matches as complete.

Only synthetic in-memory RSS; no web, email, scheduler, storage or real media.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from monitor import inspect
from unified_ministry_word import build_unified_word

PROFILE = json.loads(Path("sources.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)
DAY = date(2026, 10, 17)
PUBDAY = "Sat, 17 Oct 2026 12:00:00 +0300"


def original_items(count: int, *, same_link=False, relevant=True) -> bytes:
    items = []
    for i in range(count):
        link_id = 0 if same_link else i
        title = "وزارة التخطيط تناقش الملفات" if relevant else "بورصة وسوق المال"
        items.append(
            f"<item><title>{title}</title>"
            f"<link>https://hapijournal.com/news/rasd-{link_id}</link>"
            f"<pubDate>{PUBDAY}</pubDate></item>"
        )
    return ("<rss><channel>" + "".join(items) +
            "</channel></rss>").encode("utf-8")


class OfficialOlderOnly:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def discover_page(self, page_number):
        return ["https://mped.gov.eg/singlenews?id=7267&lang=ar"] if page_number == 1 else []

    def inspect(self, url, *, keywords, target_day, image):
        return {"status": "OUT_OF_WINDOW", "published_date_cairo": "2026-10-16"}


def feed_factory(count, *, same_link=False, relevant=True):
    material = original_items(count, same_link=same_link, relevant=relevant)
    empty = b"<rss><channel/></rss>"

    def fetch(url, limit):
        if url == PROFILE["feeds"][0]["url"]:
            return material
        if url == PROFILE["feeds"][1]["url"]:
            return empty
        raise AssertionError("unapproved source contacted")

    return fetch


class WordCandidatePoolNoSilentLossTests(unittest.TestCase):
    def test_201_distinct_matches_marks_default_preview_as_bounded(self):
        preview = inspect(PROFILE, fetch=feed_factory(201), now=NOW)
        self.assertEqual(preview["planning_headline_matches"], 201)
        self.assertEqual(len(preview["matched_public_articles"]), 15)
        self.assertTrue(preview["matched_article_pool_truncated"])
        self.assertFalse(preview["email_sent"])
        self.assertFalse(preview["scheduler_enabled"])

    def test_201_distinct_matches_marks_full_word_pool_incomplete(self):
        pool = inspect(PROFILE, fetch=feed_factory(201), now=NOW,
                       require_complete_items=True, article_limit=200)
        self.assertEqual(pool["planning_headline_matches"], 201)
        self.assertEqual(len(pool["matched_public_articles"]), 200)
        self.assertTrue(pool["matched_article_pool_truncated"])
        self.assertTrue(all(s["status"] == "ok" for s in pool["sources"]))

    def test_exact_200_is_not_prematurely_called_pool_truncation(self):
        pool = inspect(PROFILE, fetch=feed_factory(200), now=NOW,
                       require_complete_items=True, article_limit=200)
        self.assertEqual(pool["planning_headline_matches"], 200)
        self.assertEqual(len(pool["matched_public_articles"]), 200)
        self.assertFalse(pool["matched_article_pool_truncated"])

    def test_unrelated_items_do_not_fake_ministry_match_overflow(self):
        pool = inspect(PROFILE, fetch=feed_factory(201, relevant=False),
                       now=NOW, require_complete_items=True, article_limit=200)
        self.assertEqual(pool["planning_headline_matches"], 0)
        self.assertFalse(pool["matched_article_pool_truncated"])

    def test_identical_original_urls_deduplicated_before_limit(self):
        pool = inspect(PROFILE, fetch=feed_factory(201, same_link=True),
                       now=NOW, require_complete_items=True, article_limit=200)
        self.assertEqual(pool["planning_headline_matches"], 1)
        self.assertEqual(len(pool["matched_public_articles"]), 1)
        self.assertFalse(pool["matched_article_pool_truncated"])

    def test_full_word_201_candidates_is_hold_no_docx_and_named_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = Path(folder) / "sources.json"
            cfg.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
            out = Path(folder) / "word"
            result = build_unified_word(
                cfg, out, target_day=DAY, now=NOW,
                fetch=feed_factory(201), official_driver_factory=OfficialOlderOnly,
                capture=lambda *args: self.fail("must not try to capture partial pool"),
            )
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("rss_candidate_pool_exceeded_no_truncation", result["failures"])
            self.assertIn("above_15_article_production_cap_no_truncation", result["failures"])
            self.assertTrue(result["all_sources_healthy"])
            self.assertFalse(result["word_created"])
            self.assertFalse(list(out.glob("*.docx")))
            self.assertFalse(result["email_sent"])
            self.assertFalse(result["scheduler_enabled"])

    def test_exact_200_may_still_hold_for_existing_15_item_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = Path(folder) / "sources.json"
            cfg.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
            out = Path(folder) / "word"
            result = build_unified_word(
                cfg, out, target_day=DAY, now=NOW,
                fetch=feed_factory(200), official_driver_factory=OfficialOlderOnly,
                capture=lambda *args: self.fail("over 15 should never capture"),
            )
            self.assertEqual(result["status"], "HOLD")
            self.assertNotIn("rss_candidate_pool_exceeded_no_truncation", result["failures"])
            self.assertIn("above_15_article_production_cap_no_truncation", result["failures"])
            self.assertFalse(list(out.glob("*.docx")))

    def test_original_publishers_and_four_terms_unchanged(self):
        self.assertEqual(PROFILE["keywords"], [
            "وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
            "التخطيط والتنمية الاقتصادية",
        ])
        self.assertEqual([feed["url"] for feed in PROFILE["feeds"]], [
            "https://hapijournal.com/feed/",
            "https://www.almasryalyoum.com/rss/rssfeeds",
        ])


if __name__ == "__main__":
    unittest.main()
