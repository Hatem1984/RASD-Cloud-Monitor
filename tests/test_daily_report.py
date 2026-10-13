"""Offline acceptance of Arabic Word/PDF digest; fake RSS only, no SMTP or network."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from daily_report import gather, generate, render_docx, render_html

NOW = datetime(2026, 10, 13, 3, 10, tzinfo=timezone.utc)
HAPI = "https://hapijournal.com/feed/"
MASRY = "https://www.almasryalyoum.com/rss/rssfeeds"
PLANNING_URL = "https://hapijournal.com/planning-current-news"
SECOND_URL = "https://www.almasryalyoum.com/news/details/12345"
TITLE = "وزارة التخطيط تراجع مؤشرات الأداء"
SECOND_TITLE = "وزيرة التخطيط تستعرض خطة التنمية"
CONFIG = json.loads(Path("sources.json").read_text(encoding="utf-8"))
PUBLISHED = "Tue, 13 Oct 2026 02:30:00 +0000"


def xml(items):
    return ("<rss><channel>" + "".join(
        f"<item><title>{title}</title><link>{url}</link><pubDate>{date}</pubDate></item>"
        for title, url, date in items
    ) + "</channel></rss>").encode()


def fetch_both(url, limit):
    if url == HAPI:
        return xml([(TITLE, PLANNING_URL, PUBLISHED)])
    if url == MASRY:
        return xml([(SECOND_TITLE, SECOND_URL, "Tue, 13 Oct 2026 01:30:00 +0000")])
    raise AssertionError("Unexpected source")


class DailyReportTests(unittest.TestCase):
    def test_two_real_domain_mock_headlines_are_selected_and_ordered(self):
        report = gather(CONFIG, fetch=fetch_both, now=NOW)
        self.assertEqual(report["coverage"], "HEALTHY")
        self.assertEqual(len(report["articles"]), 2)
        self.assertEqual([a["url"] for a in report["articles"]], [PLANNING_URL, SECOND_URL])
        self.assertFalse(report["email_sent"])
        self.assertFalse(report["scheduler_enabled"])
        self.assertFalse(report["private_state_used"])
        self.assertIn("2026-10-13", report["window_end_cairo"])

    def test_no_matches_still_creates_valid_word_and_html_without_inventing_news(self):
        report = gather(CONFIG,
                        fetch=lambda url, limit: xml([
                            ("الأخبار الرياضية اليوم", PLANNING_URL, PUBLISHED)
                        ]) if url == HAPI else xml([]), now=NOW)
        self.assertEqual(len(report["articles"]), 0)
        self.assertIn("لم يُعثر", render_html(report))
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "daily.docx"
            render_docx(report, target)
            self.assertGreater(target.stat().st_size, 3000)
            with zipfile.ZipFile(target) as archive:
                doc_xml = archive.read("word/document.xml").decode("utf-8")
                self.assertIn("لم يُعثر", doc_xml)
                self.assertIn("w:bidi", doc_xml)

    def test_historical_undated_and_future_dated_items_are_not_reported(self):
        def mixed(url, limit):
            if url != HAPI:
                return xml([])
            return xml([
                (TITLE, PLANNING_URL, "Mon, 13 Oct 2025 00:00:00 GMT"),
                (TITLE, SECOND_URL, "Tue, 13 Oct 2026 05:00:00 GMT"),
                (TITLE, "https://hapijournal.com/undated", ""),
            ])
        report = gather(CONFIG, fetch=mixed, now=NOW)
        self.assertEqual(report["articles"], [])

    def test_report_rejects_html_markup_in_untrusted_rss_title(self):
        evil = '<script>alert("evil")</script> وزارة التخطيط'
        report = gather(CONFIG, fetch=lambda url, limit:
                        xml([(evil.replace("&", "&amp;").replace("<", "&lt;")
                                  .replace(">", "&gt;"), PLANNING_URL, PUBLISHED)])
                        if url == HAPI else xml([]), now=NOW)
        html = render_html(report)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("وزارة التخطيط", html)

    def test_partial_feed_failure_is_explicitly_degraded(self):
        def unstable(url, limit):
            if url == HAPI:
                raise TimeoutError("simulated failure")
            return xml([(SECOND_TITLE, SECOND_URL, PUBLISHED)])
        report = gather(CONFIG, fetch=unstable, now=NOW)
        self.assertEqual(report["coverage"], "DEGRADED")
        self.assertEqual(len(report["articles"]), 1)
        self.assertEqual(report["sources"][0]["error_type"], "TimeoutError")
        self.assertIn("تغطية متدهورة", render_html(report))

    def test_all_sources_down_abort_instead_of_fabricating_empty_report(self):
        with self.assertRaisesRegex(RuntimeError, "all_public_RSS_sources_failed"):
            gather(CONFIG, fetch=lambda url, limit: (_ for _ in ()).throw(
                TimeoutError("simulated")), now=NOW)

    def test_word_contains_validated_original_links_with_only_public_content(self):
        report = gather(CONFIG, fetch=fetch_both, now=NOW)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "report.docx"
            render_docx(report, target)
            with zipfile.ZipFile(target) as archive:
                body = archive.read("word/document.xml").decode("utf-8")
                links = archive.read("word/_rels/document.xml.rels").decode("utf-8")
            self.assertIn(TITLE, body)
            self.assertIn(SECOND_TITLE, body)
            self.assertIn(PLANNING_URL, links)
            self.assertIn(SECOND_URL, links)
            self.assertIn("w:bidi", body)
            self.assertNotIn("RASD_GMAIL_APP_PASSWORD", body)

    def test_pdf_and_docx_share_one_exact_source_snapshot(self):
        report_calls = []
        def once(url, limit):
            report_calls.append(url)
            return fetch_both(url, limit)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cfg = root / "sources.json"
            cfg.write_text(json.dumps(CONFIG), encoding="utf-8")
            def fake_pdf(report, dest):
                self.assertEqual(len(report["articles"]), 2)
                self.assertTrue((root / "out" / "RASD-Daily-2026-10-13.docx").is_file())
                dest.write_bytes(b"%PDF-1.7\n" + b"P" * 5000)
            with patch("daily_report.render_pdf", side_effect=fake_pdf):
                output = generate(cfg, root / "out", fetch=once, now=NOW)
            self.assertTrue(output["word_created"] and output["pdf_created"])
            self.assertEqual(len(report_calls), 2)  # one read per publisher only
            self.assertEqual(output["articles"], 2)
            self.assertFalse(output["email_sent"])
            self.assertFalse(output["scheduler_enabled"])


if __name__ == "__main__":
    unittest.main()
