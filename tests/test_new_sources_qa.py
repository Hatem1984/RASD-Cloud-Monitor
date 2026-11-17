"""Offline contract for new-first-party source qualification; no external calls."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from rasd_new_sources_qa import (CANDIDATES, observe_all,
                                  probe_candidate, fetch_direct)

NOW = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)
RSS = (b'<rss><channel><item>'
       b'<title>Egypt Ministry of Planning approves national programme</title>'
       b'<link>https://amwalalghad.com/news/first-party-example</link>'
       b'<pubDate>Tue, 17 Nov 2026 07:00:00 +0000</pubDate>'
       b'</item></channel></rss>')


class NewPublisherQA(unittest.TestCase):
    def test_known_native_candidate_is_rss_only_no_activation(self):
        row = CANDIDATES[0]
        def fetch(url, hosts):
            self.assertEqual(url, row[2])
            self.assertIn("amwalalghad.com", hosts)
            return RSS
        out = probe_candidate(row, ["Egypt Ministry of Planning"], NOW,
                              fetch=fetch)
        self.assertEqual(out["status"], "RSS_ONLY_QA")
        self.assertEqual(out["strict_original_links"], 1)
        self.assertEqual(out["keyword_matches"], 1)
        self.assertIs(out["original_page_screenshot_verified"], False)

    def test_bad_xml_and_foreign_source_are_hold_not_silent_accept(self):
        bad = probe_candidate(CANDIDATES[0], [], NOW,
                              fetch=lambda *_: b'<html>invalid</html>')
        self.assertEqual(bad["status"], "HOLD")
        self.assertEqual(bad["strict_original_links"], 0)
        self.assertIs(bad["original_page_screenshot_verified"], False)

    def test_untrusted_exception_strings_never_enter_public_results(self):
        def forbidden(_url, _hosts):
            raise RuntimeError("token=secret https://private.example/xxx")
        out = probe_candidate(CANDIDATES[1], [], NOW, fetch=forbidden)
        self.assertEqual(out["reason"], "RuntimeError")
        self.assertNotIn("secret", str(out))
        self.assertNotIn("private.example", str(out))

    def test_no_auto_admission_or_mail_for_any_candidate(self):
        config = {"feeds": [{"id": "hapi"}], "keywords": []}
        observed = observe_all(config, now=NOW, fetch=lambda *_: RSS)
        self.assertEqual(observed["candidate_count"], 5)
        self.assertEqual(observed["new_production_sources_activated"], 0)
        self.assertEqual(observed["emails_sent"], 0)
        self.assertFalse(observed["screenshots_and_word_created"])

    def test_cross_origin_or_plain_http_never_fetches(self):
        for address in ("http://amwalalghad.com/feed/",
                        "https://attacker.invalid/feed/",
                        "https://user:pass@amwalalghad.com/feed/"):
            with self.subTest(address=address):
                with self.assertRaises(ValueError):
                    fetch_direct(address, ("amwalalghad.com",))


if __name__ == "__main__":
    unittest.main()
