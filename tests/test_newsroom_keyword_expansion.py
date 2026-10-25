"""RASD: expanded Planning Ministry keywords + fifth genuine native newsroom RSS.

Offline-only tests. Never email, screenshot a public site or access private ledger.
"""
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from capture_public import allowed_url
from gate11_runner import candidate_from_feed
from monitor import article_id, inspect, parse_rss, read_feed


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
CONFIG = json.loads((ROOT / "sources_newsroom_active.json").read_text(encoding="utf-8"))
MASRAWY = next(x for x in CONFIG["feeds"] if x["id"] == "masrawy")
ARTICLE = "https://www.masrawy.com/news/news_egypt/details/2026/10/25/12345/rasd-planning"
OTHER = "https://www.masrawy.com/news/news_egypt/details/2026/10/25/98765/other"


def sample_rss(headline, url=ARTICLE, description=""):
    # Native structurally complete source item; no fabricated publisher text
    # enters actual production because tests never call the network.
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<rss version="2.0"><channel><item><title>' + headline
            + '</title><link>' + url
            + '</link><description>' + description
            + '</description><pubDate>Sun, 25 Oct 2026 11:00:00 +0000'
            '</pubDate></item></channel></rss>').encode("utf-8")


class SourceExpansionTests(unittest.TestCase):
    def test_new_publisher_is_exactly_one_new_domain(self):
        self.assertEqual(len(CONFIG["feeds"]), 5)
        self.assertEqual(CONFIG["feeds"][:4], [
            json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))["feeds"][0],
            json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))["feeds"][1],
            json.loads((ROOT / "sources_shorouk.json").read_text(encoding="utf-8"))["feeds"][0],
            CONFIG["feeds"][3],
        ])
        self.assertTrue(allowed_url(ARTICLE, "masrawy.com"))
        self.assertFalse(allowed_url(
            "https://masrawy.com.evil.example/news/news_egypt", "masrawy.com"))
        self.assertFalse(allowed_url(
            "http://www.masrawy.com/news/news_egypt", "masrawy.com"))
        self.assertFalse(allowed_url(
            "https://www.masrawy.com:8443/news/news_egypt", "masrawy.com"))
        self.assertFalse(allowed_url(
            "https://news.google.com/rss/articles/123", "masrawy.com"))

    def test_exact_native_feed_url_enforced_before_any_request(self):
        with self.assertRaisesRegex(ValueError, "feed_endpoint_not_reviewed"):
            read_feed(MASRAWY["url"] + "?extra=1", 10_000)
        with self.assertRaisesRegex(ValueError, "feed_endpoint_not_reviewed"):
            read_feed(MASRAWY["url"].replace("www.masrawy.com", "malicious.invalid"), 10_000)

    def test_expanded_keyword_in_publisher_headline(self):
        total, found = parse_rss(
            sample_rss("المعهد القومي للتخطيط يناقش خطة الدولة"),
            MASRAWY, CONFIG["keywords"], now=NOW, require_complete_items=True)
        self.assertEqual((total, len(found)), (1, 1))
        self.assertEqual(found[0]["id"], article_id(ARTICLE))
        self.assertEqual(found[0]["match_origin"], "title")
        candidate = candidate_from_feed(found[0], CONFIG, NOW)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["publisher"], "masrawy.com")

    def test_planning_phrase_in_rss_description_is_recognized(self):
        total, found = parse_rss(
            sample_rss("بدء اجتماع مجلس الوزراء",
                       description="عرض الخطة الاستثمارية للدولة للسنة الجديدة"),
            MASRAWY, CONFIG["keywords"], now=NOW, require_complete_items=True)
        self.assertEqual((total, len(found)), (1, 1))
        self.assertEqual(found[0]["match_origin"], "publisher_description")

    def test_broad_economic_or_sports_stories_stay_excluded(self):
        for title in ("تنمية الإيرادات في قطاع البنوك",
                      "وزير المالية يبحث الشراكة الاستثمارية",
                      "أزمة التخطيط لمباراة كرة القدم",
                      "البورصة تسجل ارتفاعاً في تعاملات اليوم",
                      "رؤية مصر 2030 في إحدى الفعاليات"):
            with self.subTest(title=title):
                total, found = parse_rss(
                    sample_rss(title, url=OTHER), MASRAWY,
                    CONFIG["keywords"], now=NOW, require_complete_items=True)
                self.assertEqual((total, len(found)), (1, 0))

    def test_unsafe_google_aggregator_and_broken_metadata_rejected(self):
        total, found = parse_rss(
            sample_rss("وزارة التخطيط" ,
                       url="https://news.google.com/rss/articles/123"),
            MASRAWY, CONFIG["keywords"], now=NOW)
        self.assertEqual((total, len(found)), (0, 0))
        with self.assertRaisesRegex(ValueError,
                                    "rss_original_item_identity_unverifiable"):
            parse_rss(sample_rss("وزارة التخطيط",
                                 url="https://news.google.com/rss/articles/123"),
                      MASRAWY, CONFIG["keywords"], now=NOW,
                      require_complete_items=True)

    def test_partial_new_publisher_failure_is_explicit_not_fake_success(self):
        # Existing healthy source must not disappear just because the fifth fails.
        first = CONFIG["feeds"][0]
        cfg = dict(CONFIG, feeds=[first, MASRAWY])
        def stub_fetch(url, _limit):
            if url == first["url"]:
                return sample_rss("وزير التخطيط يتحدث",
                                  url="https://hapijournal.com/planning-news")
            raise TimeoutError("offline publisher refused")
        observed = inspect(cfg, fetch=stub_fetch, now=NOW,
                           require_complete_items=True)
        self.assertEqual([s["status"] for s in observed["sources"]],
                         ["ok", "failed"])
        self.assertEqual(observed["planning_headline_matches"], 1)
        self.assertFalse(observed["email_sent"])
        self.assertFalse(observed["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
