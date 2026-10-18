"""Stage2 unified Ministry report acceptance: only simulated original publishers."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from docx import Document
from cloud_proof_report import word_images_match_capture_digests
from monitor import article_id
from unified_ministry_word import build_unified_word

PROFILE = json.loads(Path("sources.json").read_text(encoding="utf-8"))
DAY = date(2026, 10, 17)
NOW = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
OFFICIAL = "https://mped.gov.eg/singlenews?id=7269&lang=ar"
OFFICIAL2 = "https://mped.gov.eg/singlenews?id=7267&lang=ar"
RSS_URL = "https://hapijournal.com/news/ministry-20261017"
TITLE = "وزير التخطيط يعرض استراتيجية تنمية رأس المال البشري"
RSS_TITLE = "وزارة التخطيط تبحث خطة التنمية الاقتصادية"


def jpeg(dest, unique):
    image = Image.new("RGB", (1200, 900), "white")
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 1199, 190), fill=(23, 48, 86))
    for y in range(200, 840, 30):
        d.rectangle((25, y, 1170, y + 16), fill=(38, 82, 120))
    d.rectangle((40, 300, 600, 340), fill=(
        100, 40 + unique * 10, 120))
    image.save(dest, quality=90)
    return hashlib.sha256(Path(dest).read_bytes()).hexdigest()


def rss(entries):
    values = "".join(
        "<item><title>" + title + "</title><link>" + url +
        "</link><pubDate>" + when + "</pubDate></item>"
        for title, url, when in entries)
    return ("<rss><channel>" + values + "</channel></rss>").encode()


def feed(url, limit, *, fail_hapi=False, include_rss=True):
    if "hapijournal" in url:
        if fail_hapi:
            raise TimeoutError("synthetic feed failure")
        return rss([(RSS_TITLE, RSS_URL, "Sat, 17 Oct 2026 08:00:00 GMT")]
                   if include_rss else [])
    if "almasryalyoum" in url:
        return rss([])
    raise AssertionError("Unexpected feed")


class FakeDriver:
    urls = [OFFICIAL]
    blocked = set()
    offday = set()
    bad_image = set()
    list_changed = False
    pages = None

    def __init__(self):
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def discover_page(self, page_number):
        self.calls += 1
        result = (self.pages.get(page_number, [])[:]
                  if self.pages is not None else
                  (self.urls[:] if page_number == 1 else []))
        if self.list_changed and self.calls % 2 == 0 and page_number == 1:
            return result[:-1]
        return result

    def discover(self):
        return self.discover_page(1)

    def inspect(self, url, *, keywords, target_day, image):
        assert target_day == DAY
        if url in self.blocked:
            return {"status": "HOLD", "reason": "official_article_unavailable"}
        if url in self.offday:
            return {"status": "OUT_OF_WINDOW",
                    "published_date_cairo": "2026-10-16"}
        if url in self.bad_image:
            return {"status": "verified", "id": article_id(url),
                    "headline": TITLE, "sha256": "a" * 64,
                    "published_date_cairo": "2026-10-17"}
        digest = jpeg(image, self.urls.index(url) + 2)
        return {
            "status": "verified", "id": article_id(url),
            "headline": TITLE + " " + str(self.urls.index(url)),
            "sha256": digest, "published_date_cairo": "2026-10-17",
        }


def capture(url, publisher, destination):
    assert url == RSS_URL
    assert publisher == "hapijournal.com"
    digest = jpeg(destination, 1)
    return {"ok": True, "actual_url": url,
            "title": RSS_TITLE, "sha256": digest}


def execute(work, *, driver=FakeDriver, fail_hapi=False, include_rss=True,
            capture_fn=capture, now=NOW):
    config_path = Path(work) / "profile.json"
    config_path.write_text(json.dumps(PROFILE, ensure_ascii=False))
    return build_unified_word(
        config_path, Path(work) / "out", target_day=DAY, now=now,
        fetch=lambda url, limit: feed(
            url, limit, fail_hapi=fail_hapi, include_rss=include_rss),
        official_driver_factory=driver, capture=capture_fn,
    )


class UnifiedOriginalPublisherWordTests(unittest.TestCase):
    def setUp(self):
        FakeDriver.urls = [OFFICIAL]
        FakeDriver.blocked = set()
        FakeDriver.offday = set()
        FakeDriver.bad_image = set()
        FakeDriver.list_changed = False
        FakeDriver.pages = None

    def test_combines_real_publisher_types_and_inserts_sha_verifiable_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp)
            self.assertEqual(result["status"], "READY_QA_ONLY")
            self.assertEqual(result["rss_matched_on_day"], 1)
            self.assertEqual(result["official_same_day"], 1)
            self.assertEqual(result["selected_unique_articles"], 2)
            self.assertEqual(result["screenshots_verified"], 2)
            self.assertEqual(result["screenshots_missing"], 0)
            self.assertTrue(result["word_images_verified"])
            self.assertTrue(result["all_sources_healthy"])
            self.assertFalse(result["email_sent"])
            self.assertFalse(result["scheduler_enabled"])
            word = list((Path(tmp) / "out").glob("*.docx"))
            self.assertEqual(len(word), 1)
            doc = Document(word[0])
            self.assertEqual(len(doc.inline_shapes), 2)
            body = "\n".join(p.text for p in doc.paragraphs)
            self.assertIn("الساعة غير منشورة", body)
            self.assertIn("جريدة حابي", body)
            self.assertIn("وزارة التخطيط — الموقع الرسمي", body)
            self.assertNotIn("25 خبر", body)

    def test_one_failed_rss_screenshot_holds_complete_document(self):
        def never_capture(*args):
            return {"ok": False, "reason": "publisher_access_refused"}
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp, capture_fn=never_capture)
            self.assertEqual(result["status"], "HOLD")
            self.assertEqual(result["screenshots_verified"], 1)
            self.assertEqual(result["screenshots_missing"], 1)
            self.assertEqual(result["failures"]["evidence_incomplete"], 1)
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_one_failed_official_original_page_holds_word(self):
        FakeDriver.blocked = {OFFICIAL}
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp)
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("official_article_unavailable", result["failures"])
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_lost_feed_fails_entire_report_even_if_official_page_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp, fail_hapi=True)
            self.assertFalse(result["all_sources_healthy"])
            self.assertEqual(result["status"], "HOLD")
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_official_only_day_succeeds_when_other_sources_healthy_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp, include_rss=False)
            self.assertEqual(result["status"], "READY_QA_ONLY")
            self.assertEqual(result["selected_unique_articles"], 1)
            self.assertEqual(result["screenshots_verified"], 1)

    def test_off_day_original_page_is_not_reported_as_today(self):
        FakeDriver.offday = {OFFICIAL}
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp)
            self.assertEqual(result["official_offday"], 1)
            self.assertEqual(result["rss_matched_on_day"], 1)
            self.assertEqual(result["selected_unique_articles"], 1)
            self.assertEqual(result["status"], "READY_QA_ONLY")

    def test_official_index_snapshot_change_holds_without_partial_word(self):
        FakeDriver.list_changed = True
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp)
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("official_index_unavailable", result["failures"])
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_no_articles_is_hold_not_an_empty_final_word(self):
        FakeDriver.offday = {OFFICIAL}
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp, include_rss=False)
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("no_matching_articles_on_target_day", result["failures"])
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_lie_about_original_photo_sha_is_rejected(self):
        FakeDriver.bad_image = {OFFICIAL}
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp)
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("official_screenshot_missing", result["failures"])
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_above_15_never_silently_truncates_a_report(self):
        FakeDriver.urls = [
            f"https://mped.gov.eg/singlenews?id={i}&lang=ar"
            for i in range(7100, 7116)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp, include_rss=False)
            self.assertEqual(result["selected_unique_articles"], 16)
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("above_15_article_production_cap_no_truncation",
                          result["failures"])
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_two_pages_with_older_cutoff_converge_into_one_word(self):
        FakeDriver.pages = {1: [OFFICIAL], 2: [OFFICIAL2]}
        FakeDriver.offday = {OFFICIAL2}
        FakeDriver.urls = [OFFICIAL, OFFICIAL2]
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp)
            self.assertEqual(result["status"], "READY_QA_ONLY")
            self.assertEqual(result["official_index_urls"], 2)
            self.assertEqual(result["official_pages_checked"], 2)
            self.assertTrue(result["official_pagination_complete"])
            self.assertEqual(result["official_pagination_termination"], "OLDER_THAN_TARGET")
            self.assertEqual(result["official_offday"], 1)
            self.assertEqual(result["selected_unique_articles"], 2)

    def test_repeated_paged_results_hold_without_word(self):
        FakeDriver.pages = {1: [OFFICIAL], 2: [OFFICIAL]}
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp)
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("official_index_unavailable", result["failures"])
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_source_pages_out_of_chronological_order_hold(self):
        third = "https://mped.gov.eg/singlenews?id=7264&lang=ar"
        # Page1 still has a 17 October article, hence pagination
        # continues; page2 improperly jumps from the 16th back to the 17th.
        FakeDriver.pages = {1: [OFFICIAL, OFFICIAL2], 2: [third]}
        FakeDriver.offday = {OFFICIAL2}
        FakeDriver.urls = [OFFICIAL, OFFICIAL2, third]
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp)
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("official_archive_not_reverse_chronological",
                          result["failures"])
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_uncertified_depth_limit_holds_not_partial_report(self):
        urls = [
            f"https://mped.gov.eg/singlenews?id={z}&lang=ar"
            for z in range(7100, 7104)
        ]
        FakeDriver.urls = urls
        FakeDriver.pages = {i + 1: [u] for i, u in enumerate(urls)}
        with tempfile.TemporaryDirectory() as tmp:
            result = execute(tmp, include_rss=False)
            self.assertEqual(result["status"], "HOLD")
            self.assertIn("official_pagination_depth_exceeded", result["failures"])
            self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_two_independent_cairo_target_days_do_not_include_other_days(self):
        class DatedOneDayDriver(FakeDriver):
            def inspect(self, url, *, keywords, target_day, image):
                return {"status": "OUT_OF_WINDOW",
                        "published_date_cairo": "2026-10-17"}
        for target, run_clock in (
            (date(2026, 10, 16), datetime(2026, 10, 17, 9, tzinfo=timezone.utc)),
            (date(2026, 10, 18), datetime(2026, 10, 18, 9, tzinfo=timezone.utc)),
        ):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp) / "sources.json"
                source.write_text(json.dumps(PROFILE, ensure_ascii=False))
                result = build_unified_word(
                    source, Path(tmp) / "out", target_day=target, now=run_clock,
                    fetch=lambda url, limit: feed(url, limit, include_rss=False),
                    official_driver_factory=DatedOneDayDriver,
                    capture=capture)
                self.assertEqual(result["status"], "HOLD")
                self.assertEqual(result["selected_unique_articles"], 0)
                self.assertEqual(result["screenshots_verified"], 0)
                self.assertFalse(list((Path(tmp) / "out").glob("*.docx")))

    def test_disallowed_profile_or_naive_clock_aborts_before_any_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "unified_clock_must_be_aware"):
                execute(tmp, now=NOW.replace(tzinfo=None))
            config = Path(tmp) / "changed.json"
            changed = {**PROFILE, "keywords": ["اقتصاد"]}
            config.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "unified_saved_keywords_changed"):
                build_unified_word(config, Path(tmp) / "out",
                                   target_day=DAY, now=NOW,
                                   fetch=lambda *a: self.fail("unexpected fetch"))
            with self.assertRaisesRegex(ValueError, "unified_day_outside_safe_window"):
                build_unified_word(config, Path(tmp) / "out",
                                   target_day=date(2026, 1, 1), now=NOW,
                                   fetch=lambda *a: self.fail("unexpected fetch"))


if __name__ == "__main__":
    unittest.main()
