"""Test candidate source observation independently of browser and private mail."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import rasd_reference_source_probe as probe

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)


class CandidateOnlySourceQA(unittest.TestCase):
    def config(self):
        return {
            "candidates": [
                {"id": "youm7_reports", "publisher": "اليوم السابع",
                 "rss_candidate": "https://www.youm7.com/rss/SectionRss?SectionID=97",
                 "allowed_article_hosts": ["www.youm7.com"]},
                {"id": "daralmaref", "publisher": "بوابة دار المعارف",
                 "rss_candidate": None},
            ],
        }

    def test_strict_xml_candidate_does_not_activate_source(self):
        with patch.object(probe, "parse_rss", return_value=(11, [{"url":"example"}])):
            result = probe.strict_candidate_probe(
                self.config(), fetch=lambda _url, _limit: b"only-mock",
                clock=NOW)
        self.assertEqual(result["candidates"][0]["status"], "RSS_QA_ONLY")
        self.assertEqual(result["candidates"][0]["original_links"], 11)
        self.assertEqual(result["candidates"][1]["status"], "HOLD")
        self.assertFalse(result["active_feeds_modified"])
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["scheduler_enabled"])

    def test_malformed_xml_fails_closed_and_does_not_leak_server_reply(self):
        def fail(*_args, **_kwargs):
            raise ValueError("untrusted body: private-token-abc")
        with patch.object(probe, "parse_rss", side_effect=fail):
            result = probe.strict_candidate_probe(
                self.config(), fetch=lambda _url, _limit: b"not valid",
                clock=NOW)
        first = result["candidates"][0]
        self.assertEqual(first["status"], "HOLD")
        self.assertEqual(first["reason"], "ValueError")
        self.assertNotIn("private-token-abc", repr(result))

    def test_reject_unsafe_candidate_id_before_request(self):
        config = self.config()
        config["candidates"][0]["id"] = "unsafe\ntext"
        with self.assertRaisesRegex(ValueError, "candidate_id_not_safe"):
            probe.strict_candidate_probe(config, fetch=lambda *_: self.fail("network"))

    def test_reject_naive_clock(self):
        with self.assertRaisesRegex(ValueError, "candidate_clock_must_have_timezone"):
            probe.strict_candidate_probe(
                self.config(), clock=datetime(2026, 11, 14, 12))


if __name__ == "__main__":
    unittest.main()
