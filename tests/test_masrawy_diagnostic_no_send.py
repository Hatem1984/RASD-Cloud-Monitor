"""Pure tests for bounded original-Masrawy diagnosis; no network."""
import unittest
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from rasd_masrawy_diagnostic_no_send import diagnose, sample_indices


class MasrawyDiagnosticNoSend(unittest.TestCase):
    def test_first_and_last_only_no_unbounded_pages(self):
        self.assertEqual(sample_indices(30), [0, 1, 2, 3, 26, 27, 28, 29])
        self.assertEqual(sample_indices(5), [0, 1, 2, 3, 4])
        self.assertEqual(sample_indices(0), [])
        self.assertEqual(sample_indices(30, max_checks=0), [])
        with self.assertRaises(ValueError):
            sample_indices(30, max_checks=9)

    def test_original_required_no_original_urls_in_output(self):
        feed = (
            "<rss><channel>" +
            "".join(
                "<item><title>وزارة التخطيط تعلن تقريرا جديدا رقم "
                + str(i) + "</title>"
                + "<link>https://www.masrawy.com/news/test/"
                + str(i) + "</link>"
                + "<pubDate>11/17/2026 06:00:00 PM</pubDate>"
                + "</item>"
                for i in range(10)) + "</channel></rss>"
        ).encode()
        visits = []
        def original(url, title, stamp):
            visits.append(url)
            if url.endswith("/9"):
                raise ValueError("masrawy_original_page_request_hold")
            return datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc), stamp
        cfg = {"feeds": [{"id":"masrawy", "url":"https://www.masrawy.com/feed"}],
               "keywords":["وزارة التخطيط"],"max_feed_bytes":1500000}
        report = diagnose(cfg, read=lambda *_: feed, original=original)
        self.assertEqual(report["total_rss_items"], 10)
        self.assertEqual(report["sampled_original_pages"], 8)
        self.assertEqual(report["sample_outcomes"]["verified_original_page"], 7)
        self.assertEqual(report["failure_positions"], [
            {"position": 10, "reason":"masrawy_original_page_request_hold"}])
        self.assertEqual(report["ministry_phrase_matches_before_date_proof"], 10)
        self.assertFalse(report["all_items_original_date_verified"])
        self.assertNotIn("masrawy.com/news/test", str(report))
        self.assertFalse(report["inbox_delivery_verified"])
        self.assertEqual(len(visits), 8)

    def test_untrusted_exception_does_not_leak_sensitive_text(self):
        feed = (b"<rss><channel><item><title>Test</title>"
                b"<link>https://www.masrawy.com/news/one</link>"
                b"<pubDate>11/17/2026 06:00:00 PM</pubDate>"
                b"</item></channel></rss>")
        cfg = {"feeds":[{"id":"masrawy","url":"https://www.masrawy.com/rss"}],
               "keywords":[],"max_feed_bytes":1500000}
        result = diagnose(cfg, read=lambda *_: feed,
            original=lambda *_: (_ for _ in ()).throw(
                RuntimeError("password=secret https://private.internal/")))
        self.assertEqual(result["sample_outcomes"], {"unclassified_hold":1})
        self.assertNotIn("password", str(result))
        self.assertNotIn("private.internal", str(result))


if __name__ == "__main__":
    unittest.main()
