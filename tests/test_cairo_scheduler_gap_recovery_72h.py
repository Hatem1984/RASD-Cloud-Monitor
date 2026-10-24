"""Bounded missed-cron catch-up from approved RSS; no network, credentials or mail."""
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

from monitor import article_id
from scheduled_rasd import discover_interval_news


class MissedCronLookback(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 24, 13, 0, tzinfo=timezone.utc)
        self.config = {
            "recent_hours": 72,
            "feeds": [{
                "id": "hapi",
                "name": "Hapi native news RSS",
                "allowed_article_hosts": ["hapijournal.com"],
            }],
        }

    def article(self, hours_ago: int):
        url = f"https://hapijournal.com/news/catchup-{hours_ago}"
        return {
            "id": article_id(url),
            "headline": f"وزارة التخطيط أخبار منشورة قبل {hours_ago} ساعة",
            "url": url,
            "source": "Hapi native news RSS",
            "published": format_datetime(
                self.now - timedelta(hours=hours_ago), usegmt=True),
            "selection": "live_feed_discovery",
            "publisher_excerpt": "خبر من المصدر المعتمد فقط",
        }

    def inspector(self, rows):
        def inspect(_config, *, now, article_limit, require_complete_items):
            self.assertEqual(now, self.now)
            self.assertEqual(article_limit, 200)
            self.assertTrue(require_complete_items)
            return {
                "sources": [{"feed_id": "hapi", "status": "ok"}],
                "matched_public_articles": rows,
                "matched_article_pool_truncated": False,
            }
        return inspect

    def test_default_recovers_a_real_71_hour_rss_entry_not_only_last_day(self):
        old, recent = self.article(71), self.article(3)
        feed = self.inspector([old, recent])
        result = discover_interval_news(self.config, self.now, inspector=feed)
        self.assertEqual({a["id"] for a in result}, {old["id"], recent["id"]})
        last_day = discover_interval_news(
            self.config, self.now, inspector=feed, age_hours=24)
        self.assertEqual([a["id"] for a in last_day], [recent["id"]])

    def test_older_than_72_hours_is_not_resurrected(self):
        inside, outside = self.article(71), self.article(73)
        result = discover_interval_news(
            self.config, self.now,
            inspector=self.inspector([inside, outside]))
        self.assertEqual([a["id"] for a in result], [inside["id"]])

    def test_gap_recovery_cannot_fabricate_items_missing_from_rss(self):
        result = discover_interval_news(
            self.config, self.now, inspector=self.inspector([]))
        self.assertEqual(result, [])

    def test_lookback_cannot_be_unbounded(self):
        with self.assertRaisesRegex(ValueError, "unapproved_newsroom_lookback"):
            discover_interval_news(
                self.config, self.now, inspector=self.inspector([]),
                age_hours=96)


if __name__ == "__main__":
    unittest.main()
