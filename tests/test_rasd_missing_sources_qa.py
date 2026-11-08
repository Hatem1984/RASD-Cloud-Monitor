"""RASD five missing-publisher first-party qualification, synthetic mocks only."""
import unittest
from datetime import datetime, timezone
from email.utils import format_datetime

from rasd_missing_sources_qualification import (
    CANDIDATES, qualify, assess_rss, _one_source, _url_allowed)
from rasd_publisher_metadata_qa import assess_article_page

DATE = "2026-11-08T16:54:25+00:00"
TITLE = "Minister of Planning announces national development program"
PAGE = "https://www.dostor.org/1234567"
RSS = (f'<rss version="2.0"><channel><item><title>{TITLE}</title>'
       f'<link>{PAGE}</link><pubDate>Sun, 08 Nov 2026 16:54:25 +0000</pubDate>'
       f'</item></channel></rss>').encode()


class MissingPublisherQualificationQA(unittest.TestCase):
    def test_no_network_by_default(self):
        self.assertEqual(qualify(live=False)["status"], "DRY_RUN_NO_NETWORK")
        self.assertEqual(qualify(live=False)["activated"], 0)
        self.assertEqual(len(CANDIDATES), 5)

    def test_html_redirect_and_bad_xml_never_activate(self):
        candidate = CANDIDATES[-1]
        def fake(url, hosts):
            if url == candidate["home"]:
                return b"<html><title>home</title></html>", "text/html"
            return b"<html>not xml</html>", "text/html"
        result = _one_source(candidate, fetcher=fake)
        self.assertEqual(result["homepage"], "READABLE")
        self.assertEqual(result["rss"][0]["status"], "HOLD_NOT_FEED")
        self.assertEqual(result["activation"], "HOLD_NOT_APPROVED")

    def test_strict_feed_requires_native_host_and_explicit_date(self):
        hosts = ("www.dostor.org",)
        okay = assess_rss(RSS, hosts)
        self.assertEqual(okay["status"], "RSS_STRICT_READABLE_NOT_APPROVED")
        self.assertEqual(okay["items_seen"], 1)
        self.assertEqual(okay["sample_url"], PAGE)
        bad_date = RSS.replace(b"+0000", b"")
        self.assertEqual(assess_rss(bad_date, hosts)["status"],
                         "HOLD_AMBIGUOUS_ITEM_DATE")
        bad_host = RSS.replace(b"www.dostor.org", b"attacker.invalid")
        self.assertEqual(assess_rss(bad_host, hosts)["status"],
                         "HOLD_CROSS_HOST_ITEM")
        self.assertFalse(_url_allowed(
            "https://www.dostor.org.attacker.invalid/x", hosts))

    def test_page_title_date_metadata_match_not_screenshot(self):
        html = (f'<html><head><meta property="og:title" content="{TITLE}">'
                f'<meta property="article:published_time" content="{DATE}">'
                f'</head></html>').encode()
        result = assess_article_page(
            html, rss_title=TITLE, rss_published_utc=DATE)
        self.assertEqual(result["status"],
                         "ORIGINAL_TITLE_DATE_MATCH_NO_SCREENSHOT")
        self.assertNotIn("image_verified", result)
        self.assertEqual(
            assess_article_page(html.replace(b"2026-11-08", b"2026-11-07"),
                                rss_title=TITLE,
                                rss_published_utc=DATE)["status"],
            "HOLD_ORIGINAL_DATE_MISMATCH")

    def test_candidate_page_date_missing_is_hold(self):
        candidate = CANDIDATES[-1]
        def fake(url, hosts):
            if url == candidate["rss"][0]:
                return RSS, "application/xml"
            if url == PAGE:
                return (f'<meta property="og:title" content="{TITLE}">'
                        ).encode(), "text/html"
            return b"<html>home</html>", "text/html"
        result = _one_source(candidate, fetcher=fake)
        self.assertEqual(
            result["rss"][0]["original_article"]["status"],
            "HOLD_ORIGINAL_DATE_MISSING")
        self.assertEqual(result["activation"], "HOLD_NOT_APPROVED")


if __name__ == "__main__":
    unittest.main()
