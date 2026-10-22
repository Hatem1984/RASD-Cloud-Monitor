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

    def bounding_box(self):
        return {"x": 50, "y": 219, "width": 1120, "height": 50}


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
    viewport_size = {"width": 1200, "height": 900}

    def evaluate(self, script):
        return 0 if script == "window.scrollY" else None

    def __init__(self, headline=HEADLINE, body=BODY, status=200):
        self.headline, self.body, self.status = headline, body, status

    def goto(self, url, wait_until, timeout):
        assert url == SAMPLE
        return type("Response", (), {"status": self.status})()

    def locator(self, selector):
        return FakeLocator(self.headline if selector == "h1" else self.body)

    def screenshot(self, path, type, quality, full_page, clip, animations, timeout):
        assert type == "jpeg" and full_page is True
        assert animations == "disabled" and clip["width"] <= 1400
        image = Image.new("RGB", (1200, 1100), "#ffffff")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1199, 170), fill="#f3f5f8")
        for y in (20, 55, 90, 125):
            draw.rectangle((70, y, 1100, y + 12), fill="#193759")
        for y in range(190, 1090, 28):
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

    def test_date_immediately_before_article_heading_is_accepted_not_footer(self):
        day = "17 أكتوبر 2026"
        self.assertEqual(original_publication_date(
            "الرئيسية " + day + "\n" + HEADLINE +
            "\nأخبار الوزارة ذات الصلة", HEADLINE), date(2026, 10, 17))
        # Repeated title in source HTML must not replace a publisher date
        # with crawler clock or an unrelated footer date.
        self.assertEqual(original_publication_date(
            "العنوان: " + HEADLINE + "\n" + day +
            "\n" + HEADLINE + "\nخبر الوزارة", HEADLINE),
            date(2026, 10, 17))
        self.assertIsNone(original_publication_date(
            "31 فبراير 2026\n" + HEADLINE, HEADLINE))

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

    def test_blank_or_giant_original_frame_never_promoted(self):
        class BlankScreenshot(FakePage):
            requests = []
            def screenshot(self, path, type, quality, full_page, clip,
                           animations, timeout):
                self.requests.append((full_page, clip, animations))
                Image.new("RGB", (1200, 1100), "white").save(
                    path, format="JPEG", quality=quality)
        with tempfile.TemporaryDirectory() as work:
            page = BlankScreenshot()
            destination = Path(work) / "blank.jpg"
            result = _read_original(
                page, SAMPLE, ["وزير التخطيط"], date(2026, 10, 17), destination)
            self.assertEqual(result["status"], "HOLD")
            self.assertEqual(result["reason"], "original_page_unreadable_visual_qa")
            self.assertFalse(destination.exists())
            self.assertEqual(len(page.requests), 1)
            full_page, clip, animations = page.requests[0]
            self.assertTrue(full_page)
            self.assertLessEqual(clip["width"], 1400)
            self.assertEqual(clip["height"], 1100)
            self.assertEqual(animations, "disabled")

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
