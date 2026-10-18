"""Gate38 official source provenance/date/screenshot tests. Zero network."""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw

from cloud_proof_report import word_images_match_capture_digests
from daily_report import render_docx
from official_ministry_source import (
    INDEX, SAMPLE, _read_original, allowed_official_resource,
    canonical_official_article, index_articles, original_publication_date,
)

HEADLINE = ('وزير التخطيط يعرض مؤشرات تعافي الاقتصاد المصري '
            'ويستعرض تفاصيل برنامج التحول الاقتصادي الوطني')
BODY = 'الرئيسية\n' + HEADLINE + '\n17 أكتوبر 2026\n' + (
    'دراسة التنمية الاقتصادية وتقدم العمل بالوزارة. ' * 15)


class FakeElement:
    def __init__(self, value):
        self.value = value

    def inner_text(self, timeout=8000):
        return self.value

    def scroll_into_view_if_needed(self, timeout=4000):
        return None


class FakeLocator:
    def __init__(self, value):
        self.value = value

    @property
    def first(self):
        return FakeElement(self.value)

    def inner_text(self, timeout=8000):
        return self.value


class FakePage:
    url = SAMPLE

    def __init__(self, headline=HEADLINE, body=BODY, status=200):
        self.headline, self.body, self.status = headline, body, status

    def goto(self, url, wait_until, timeout):
        assert url == SAMPLE
        return type("Response", (), {"status": self.status})()

    def locator(self, selector):
        return FakeLocator(self.headline if selector == "h1" else self.body)

    def screenshot(self, path, type, quality, full_page, timeout):
        assert type == "jpeg" and not full_page
        image = Image.new("RGB", (1200, 900), "#ffffff")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1199, 170), fill="#193759")
        for y in range(190, 880, 28):
            draw.rectangle((50, y, 1100, y + 16), fill="#2f5067")
        image.save(path, format="JPEG", quality=quality)


class OriginalMinistrySourceOfflineTests(unittest.TestCase):
    def test_index_discovers_only_genuine_canonical_ministry_article_links(self):
        html = ('<html><body><a href="/singlenews?id=7269&lang=ar">اقرأ</a>'
                '<a href="https://www.mped.gov.eg/singlenews?lang=ar&id=7269">نفسه</a>'
                '<a href="https://mped.gov.eg/singlenews?id=7264&lang=ar">أقدم</a>'
                '<a href="https://news.google.com/rss/articles/x">تجميع</a>'
                '<a href="http://mped.gov.eg/singlenews?id=23&lang=ar">غير آمن</a>'
                '<a href="https://mped.gov.eg.evil.invalid/singlenews?id=23&lang=ar">مزيف</a>'
                '<a href="/singlenews?id=12&type=previous&lang=ar">بارامتر زائد</a>'
                '</body></html>')
        self.assertEqual(index_articles(html), [
            SAMPLE, "https://mped.gov.eg/singlenews?id=7264&lang=ar",
        ])

    def test_full_url_validation_disallows_other_hosts_queries_and_redirects(self):
        for url in [
            "http://mped.gov.eg/singlenews?id=7269&lang=ar",
            "https://mped.gov.eg.evil.invalid/singlenews?id=7269&lang=ar",
            "https://mped.gov.eg:8443/singlenews?id=7269&lang=ar",
            "https://mped.gov.eg/News?id=57&lang=ar",
            "https://mped.gov.eg/singlenews?id=7269&type=previous&lang=ar",
            "https://mped.gov.eg/singlenews?id=&lang=ar",
            "https://mped.gov.eg/singlenews?id=7269&lang=en",
            "https://mped.gov.eg/singlenews?id=-1&lang=ar",
            "https://user:pass@mped.gov.eg/singlenews?id=7269&lang=ar",
            "https://mped.gov.eg/singlenews?id=7269&lang=ar#abc",
        ]:
            with self.subTest(url=url):
                self.assertIsNone(canonical_official_article(url))
        self.assertEqual(canonical_official_article(SAMPLE), SAMPLE)
        self.assertFalse(allowed_official_resource("https://google.com/api"))

    def test_rejects_html_bloat_and_no_real_links(self):
        with self.assertRaises(ValueError):
            index_articles("x" * 1_500_001)
        self.assertEqual(index_articles('<p>لا يوجد نتائج للبحث</p>'), [])

    def test_real_arabic_original_day_is_extracted_next_to_exact_headline(self):
        self.assertEqual(original_publication_date(BODY, HEADLINE),
                         date(2026, 10, 17))
        arabic = BODY.replace("17 أكتوبر 2026", "١٧ أكتوبر ٢٠٢٦")
        self.assertEqual(original_publication_date(arabic, HEADLINE),
                         date(2026, 10, 17))
        self.assertIsNone(original_publication_date(
            HEADLINE + "\n31 فبراير 2026", HEADLINE))
        self.assertIsNone(original_publication_date(
            HEADLINE + "\n17 أكتوبر 2026 / 16 أكتوبر 2026", HEADLINE))
        self.assertIsNone(original_publication_date(
            HEADLINE + ("." * 500) + "17 أكتوبر 2026", HEADLINE))
        self.assertIsNone(original_publication_date(
            "صفحة أخرى بتاريخ 17 أكتوبر 2026", HEADLINE))

    def test_official_page_gets_genuine_page_jpeg_bound_into_one_word(self):
        with tempfile.TemporaryDirectory() as tmp:
            shot = Path(tmp) / "original.jpg"
            receipt = _read_original(
                FakePage(), SAMPLE, ["وزير التخطيط"], date(2026, 10, 17), shot)
            self.assertEqual(receipt["status"], "verified")
            self.assertEqual(receipt["published_date_cairo"], "2026-10-17")
            self.assertTrue(shot.is_file())
            report = {
                "title": "اختبار مصدر رسمي", "display_window_start": "17 أكتوبر 2026",
                "display_window_end": "17 أكتوبر 2026", "coverage": "QA",
                "verified_links": 1, "articles": [{
                    "headline": HEADLINE,
                    "source": "وزارة التخطيط — الموقع الرسمي",
                    "url": SAMPLE,
                    "published_at_cairo": "2026-10-17",
                    "published_display_cairo": "17 أكتوبر 2026",
                    "evidence_image_path": str(shot),
                }],
                "sources": [{"feed_id": "mped", "status": "ok",
                             "verified_links": 1, "error_type": None}],
                "limitations": "اختبار فقط",
            }
            word = Path(tmp) / "one.docx"
            render_docx(report, word)
            self.assertTrue(word_images_match_capture_digests(
                word, [{"status": "verified", "sha256": receipt["sha256"]}]))

    def test_genuine_full_page_fallback_rechecks_jpeg_instead_of_bypass(self):
        class FirstFrameBlank(FakePage):
            modes = []
            def screenshot(self, path, type, quality, full_page, timeout):
                self.modes.append(full_page)
                if not full_page:
                    Image.new("RGB", (1200, 900), "white").save(
                        path, format="JPEG", quality=quality)
                else:
                    super().screenshot(path, type, quality, full_page, timeout)
        with tempfile.TemporaryDirectory() as work:
            page = FirstFrameBlank()
            destination = Path(work) / "verified.jpg"
            result = _read_original(
                page, SAMPLE, ["وزير التخطيط"], date(2026, 10, 17), destination)
            self.assertEqual(page.modes, [False, True])
            self.assertEqual(result["status"], "verified")
            self.assertTrue(destination.is_file())

    def test_wrong_day_generic_headline_blocked_before_screenshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            shot = Path(tmp) / "blocked.jpg"
            for fake in [
                FakePage(status=403),
                FakePage(headline="تقرير اقتصادي لا يخص الوزارة"),
                FakePage(body=BODY.replace("17 أكتوبر 2026", "16 أكتوبر 2026")),
            ]:
                with self.subTest(fake=fake.headline, date=fake.body[:100]):
                    res = _read_original(fake, SAMPLE, [
                        "وزارة التخطيط", "وزير التخطيط",
                        "وزيرة التخطيط", "التخطيط والتنمية الاقتصادية",
                    ], date(2026, 10, 17), shot)
                    self.assertEqual(res["status"], "HOLD")
                    self.assertFalse(shot.exists())


if __name__ == "__main__":
    unittest.main()
