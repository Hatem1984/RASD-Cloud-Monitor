"""Facebook pilot tests are strictly offline; never contact Meta or send mail."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from docx import Document

from facebook_pilot import (
    _approved_pages, _permalink_ok, collect, run_manual, write_facebook_word,
)


NOW = datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)
CONFIG = {"pages": [{"id": "123456789", "name": "صفحة الوزارة"}],
          "keywords": ["وزارة التخطيط", "وزير التخطيط"]}


def sample(message="بيان صادر عن وزارة التخطيط", *,
           url="https://www.facebook.com/123456789/posts/88",
           created="2026-11-06T19:00:00+0000", ident="123456789_88"):
    return {"id": ident, "message": message,
            "permalink_url": url, "created_time": created}


class FacebookPilotTest(unittest.TestCase):
    def test_no_live_flag_never_reads_config_or_token_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "does-not-exist.json"
            result = run_manual(live=False, output_dir=Path(directory),
                                config_file=missing)
            self.assertEqual(result["status"], "DRY_RUN_NO_NETWORK")
            self.assertEqual(list(Path(directory).glob("*.docx")), [])

    def test_missing_page_approval_and_token_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "facebook_page_configuration_hold"):
            collect({"pages": [], "keywords": ["وزارة التخطيط"]},
                    token="dummy", now=NOW)
        with self.assertRaisesRegex(ValueError, "facebook_meta_authorization_hold"):
            collect(CONFIG, token="", now=NOW,
                    page_getter=lambda *_: self.fail("network forbidden"))

    def test_rejects_bad_pages_and_unauthorized_redirect_targets(self):
        for pages in ([{"id": "http://evil", "name": "غير مصرح"}],
                      [{"id": "123456789", "name": "A"},
                       {"id": "123456789", "name": "B"}]):
            with self.assertRaises(ValueError):
                _approved_pages({"pages": pages})
        self.assertFalse(_permalink_ok("https://facebook.com.evil.tld/posts/1"))
        self.assertFalse(_permalink_ok("http://www.facebook.com/posts/1"))
        self.assertFalse(_permalink_ok(
            "https://www.facebook.com/posts/1?access_token=secret"))

    def test_approved_page_post_matches_and_has_separate_word(self):
        calls = []
        def fake(page_id, token):
            calls.append((page_id, token))
            return {"data": [sample(), sample(), sample("أخبار رياضية")]}
        report = collect(CONFIG, token="test-only", page_getter=fake, now=NOW)
        self.assertEqual(calls, [("123456789", "test-only")])
        self.assertEqual(report["status"], "SAMPLED_MATCHES")
        self.assertEqual(len(report["posts"]), 1)
        self.assertEqual(report["posts"][0]["evidence_status"],
                         "META_PAGE_POST_METADATA_ONLY")
        self.assertFalse(report["email_sent"])
        with tempfile.TemporaryDirectory() as directory:
            path = write_facebook_word(
                report, Path(directory) / "RASD-Facebook-Manual.docx")
            document = Document(path)
            paragraphs = "\n".join(p.text for p in document.paragraphs)
            self.assertIn("تقرير فيسبوك التجريبي", paragraphs)
            self.assertIn("لا يثبتان صحة الادعاءات", paragraphs)
            self.assertNotIn("مآل", paragraphs)
            self.assertNotIn("روابط RSS", paragraphs)

    def test_invalid_time_and_url_are_held_not_reported(self):
        posts = [sample(url="https://attacker.example/post"),
                 sample(created="2026-11-06T19:00:00"),
                 sample(created="2026-11-07T12:00:00+0000")]
        report = collect(
            CONFIG, token="test", page_getter=lambda *_: {"data": posts}, now=NOW)
        self.assertEqual(report["posts"], [])
        self.assertEqual(report["posts_held"], 3)
        self.assertEqual(report["status"], "PARTIAL_SAMPLE")

    def test_graph_failure_is_hold_not_fake_no_news_and_no_token_leak(self):
        secret = "secret-should-never-leak"
        def fail(*_):
            raise RuntimeError("Meta response includes " + secret)
        result = collect(CONFIG, token=secret, page_getter=fail, now=NOW)
        self.assertEqual(result["pages_failed"], 1)
        self.assertEqual(result["status"], "PARTIAL_SAMPLE")
        self.assertNotIn(secret, repr(result))
        self.assertEqual(result["posts_inspected"], 0)

    def test_full_manual_requires_live_and_outputs_private_separate_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "pages.json"
            config_file.write_text(
                json.dumps({"pages": CONFIG["pages"]}), encoding="utf-8")
            with patch.dict(os.environ, {"RASD_FB_PAGE_TOKEN": "offline-token"}):
                report = run_manual(
                    live=True, output_dir=Path(directory) / "facebook",
                    config_file=config_file, now=NOW,
                    page_getter=lambda *_: {"data": [sample()]})
            self.assertEqual(report["posts"], 1)
            self.assertTrue(Path(report["word"]).is_file())
            self.assertEqual(report["email_sent"], False)
            self.assertNotIn("offline-token", repr(report))


if __name__ == "__main__":
    unittest.main()
