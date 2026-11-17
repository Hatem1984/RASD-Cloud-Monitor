"""Regression: original Masrawy dates required for relevant news, NOT unselected pages.

A real 17 Nov RSS sample had 10 items, zero matching Ministry phrases and
one unrelated original-page date discrepancy. Before this change the whole
publisher was repeatedly marked failed. No imaginary timezone or date may
ever be sent to the Ministry. Entire suite runs without HTTP or SMTP.
"""
from datetime import datetime, timezone
from email.utils import format_datetime
from unittest.mock import patch
import unittest

from monitor import inspect, parse_rss

NOW = datetime(2026, 11, 17, 17, 0, tzinfo=timezone.utc)
DATE = "11/17/2026 06:00:00 PM"
TZ_DATE = datetime.fromisoformat("2026-11-17T18:00:00+02:00")
FEED = {
    "id": "masrawy", "name": "Masrawy native Egypt news RSS",
    "url": "https://www.masrawy.com/rss/feed/35/publisher",
    "allowed_article_hosts": ["www.masrawy.com", "masrawy.com"],
}
HAPI = {
    "id": "hapi", "name": "Hapi native news RSS",
    "url": "https://hapijournal.com/feed/",
    "allowed_article_hosts": ["hapijournal.com"],
}
KEYWORDS = ["وزارة التخطيط"]
NEUTRAL = "افتتاح معرض فني في مدينة القاهرة"
RELEVANT = "وزارة التخطيط تعلن تفاصيل الخطة الاستثمارية للدولة"


def xml(rows):
    body = ""
    for index, (title, date, description, host) in enumerate(rows):
        body += (
            f"<item><title>{title}</title>"
            f"<link>https://{host}/news/news_egypt/details/2026/11/17/{index}/original</link>"
            f"<description>{description}</description>"
            f"<pubDate>{date}</pubDate></item>"
        )
    return ("<rss><channel>" + body + "</channel></rss>").encode("utf-8")


def row(title=NEUTRAL, date=DATE, description="", host="www.masrawy.com"):
    return (title, date, description, host)


class MasrawySelectiveSourceProofTests(unittest.TestCase):
    def test_ten_unrelated_original_pages_never_trigger_article_requests(self):
        data = xml([row() for _ in range(10)])
        with patch("masrawy_original_date.original_pubdate",
                   side_effect=AssertionError("unrelated original MUST NOT fetch")) as p:
            links, stories = parse_rss(data, FEED, KEYWORDS, NOW,
                                       require_complete_items=True)
        self.assertEqual(links, 10)
        self.assertEqual(stories, [])
        p.assert_not_called()

    def test_relevant_original_is_still_exactly_verified_and_sent_dated(self):
        data = xml([row(RELEVANT), row()])
        verified = (TZ_DATE, format_datetime(TZ_DATE))
        with patch("masrawy_original_date.original_pubdate",
                   return_value=verified) as p:
            links, stories = parse_rss(data, FEED, KEYWORDS, NOW,
                                       require_complete_items=True)
        self.assertEqual(links, 2)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["published"], format_datetime(TZ_DATE))
        self.assertIn("+0200", stories[0]["published"])
        p.assert_called_once()

    def test_relevant_original_unverifiable_causes_full_hold(self):
        data = xml([row(RELEVANT), row()])
        with patch("masrawy_original_date.original_pubdate",
                   side_effect=ValueError(
                       "masrawy_publisher_publication_date_unverified")) as p:
            with self.assertRaisesRegex(
                ValueError, "rss_original_item_date_unverifiable"):
                parse_rss(data, FEED, KEYWORDS, NOW,
                          require_complete_items=True)
        p.assert_called_once()

    def test_match_in_description_also_requires_original_page(self):
        data = xml([row(description="لقاء مع وزارة التخطيط")])
        with patch("masrawy_original_date.original_pubdate",
                   return_value=(TZ_DATE, format_datetime(TZ_DATE))) as p:
            _, stories = parse_rss(data, FEED, KEYWORDS, NOW,
                                   require_complete_items=True)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["match_origin"], "publisher_description")
        p.assert_called_once()

    def test_unrelated_malformed_rss_date_still_rejects_source(self):
        data = xml([row(date="not-a-publisher-date")])
        with patch("masrawy_original_date.original_pubdate") as p:
            with self.assertRaisesRegex(
                ValueError, "rss_original_item_date_unverifiable"):
                parse_rss(data, FEED, KEYWORDS, NOW,
                          require_complete_items=True)
        p.assert_not_called()

    def test_unapproved_article_link_rejected_before_any_page_read(self):
        data = xml([row(host="attacker.invalid")])
        with patch("masrawy_original_date.original_pubdate") as p:
            with self.assertRaisesRegex(
                ValueError, "rss_original_item_identity_unverifiable"):
                parse_rss(data, FEED, KEYWORDS, NOW,
                          require_complete_items=True)
        p.assert_not_called()

    def test_other_publishers_still_require_all_item_zone_dates(self):
        data = xml([row(host="hapijournal.com")])
        with self.assertRaisesRegex(
            ValueError, "rss_original_item_date_unverifiable"):
            parse_rss(data, HAPI, KEYWORDS, NOW,
                      require_complete_items=True)

    def test_conflicting_duplicate_link_date_still_rejected(self):
        original = xml([row(NEUTRAL, DATE)])
        # Same URL, changed publisher naive date; cannot silently first-wins.
        source = original.decode("utf-8")
        element = source.split("<item>")[1].split("</item>")[0]
        conflicting = element.replace(DATE, "11/17/2026 07:00:00 PM")
        data = source.replace("</channel>", "<item>" + conflicting +
                              "</item></channel>").encode("utf-8")
        with self.assertRaisesRegex(
            ValueError, "rss_original_duplicate_conflict"):
            parse_rss(data, FEED, KEYWORDS, NOW, require_complete_items=True)

    def test_public_inspection_discloses_date_verification_scope(self):
        data = xml([row(), row()])
        cfg = {"feeds": [FEED], "keywords": KEYWORDS,
               "max_feed_bytes": 1500000, "recent_hours": 72}
        with patch("masrawy_original_date.original_pubdate",
                   side_effect=AssertionError("unrelated not fetched")) as p:
            out = inspect(cfg, fetch=lambda *_: data, now=NOW,
                          require_complete_items=True, article_limit=200)
        self.assertEqual(out["sources"][0]["status"], "ok")
        self.assertEqual(out["sources"][0]["date_verification_scope"],
                         "original_page_for_relevant_items_only")
        self.assertEqual(out["matched_public_articles"], [])
        self.assertFalse(out["email_sent"])
        p.assert_not_called()


if __name__ == "__main__":
    unittest.main()
