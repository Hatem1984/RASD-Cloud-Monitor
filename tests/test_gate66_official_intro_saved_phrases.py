"""Gate66: verified Ministry-page lead matching with UNCHANGED four terms.

All network/browser/media are synthetic. A genuine news card, valid date and
real owner-review screenshot remain mandatory in the actual manual workflow.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from monitor import _ministry_term_present
from monitor import article_id
from official_ministry_source import (
    _read_original, original_headline_or_intro_matches,
)
from unified_ministry_word import OfficialPageDriver

TERMS = [
    "وزارة التخطيط", "وزير التخطيط", "وزيرة التخطيط",
    "التخطيط والتنمية الاقتصادية",
]
TITLE = (
    "وزيرا التخطيط والاستثمار في لقاء مفتوح مع 150 من طلاب "
    "الجامعات حول سوق العمل وريادة الأعمال"
)
INTRO = (
    "شارك الدكتور أحمد رستم، وزير التخطيط والتنمية الاقتصادية، "
    "في لقاء لطلاب الجامعات حول ريادة الأعمال."
)
DAY = date(2026, 10, 19)
URL = "https://mped.gov.eg/singlenews?id=7270&lang=ar"


def page_text(*, intro=INTRO, preface="", padding="") -> str:
    # The article body's real H1, nearby original date and publisher lead
    # are the sole grounds for this synthetic acceptance example.
    return (preface + " " + TITLE + " 19 أكتوبر 2026 "
            + "ملخص اللقاء: " + intro + " " + padding + " "
            + ("مناقشة التحديات والتكنولوجيا وريادة الأعمال. " * 18))


def fake_page(body: str):
    page = Mock()
    page.url = URL
    page.goto.return_value.status = 200
    page.locator.side_effect = lambda selector: (
        Mock(first=Mock(inner_text=Mock(return_value=TITLE)))
        if selector == "h1"
        else Mock(inner_text=Mock(return_value=body))
    )
    return page


class OfficialLeadMatchingRegressionTests(unittest.TestCase):
    def test_original_real_world_title_does_not_match_but_intro_does(self):
        self.assertFalse(_ministry_term_present(TITLE, TERMS))
        self.assertTrue(_ministry_term_present(INTRO, TERMS))
        self.assertTrue(original_headline_or_intro_matches(
            page_text(), TITLE, TERMS,
        ))

    def test_original_headline_alone_remains_eligible(self):
        title = "وزير التخطيط يعرض برنامج التحول الاقتصادي"
        self.assertTrue(original_headline_or_intro_matches(
            title + " 19 أكتوبر 2026 " + ("نص آخر " * 100),
            title, TERMS,
        ))

    def test_only_exact_saved_phrases_match_not_generic_planning(self):
        headline = "خبر عن الاقتصاد المصري وريادة الأعمال"
        body = headline + " 19 أكتوبر 2026 " + (
            "تطوير خطط التنمية والنمو الاقتصادي والحكومة. " * 25
        )
        self.assertFalse(original_headline_or_intro_matches(
            body, headline, TERMS,
        ))

    def test_nav_before_original_h1_cannot_make_intro_match(self):
        text = page_text(
            preface="قائمة الموقع: وزارة التخطيط والتقارير والاتصال",
            intro="مناقشة طلابية لا تتضمن أيًا من العبارات الأربع.",
        )
        self.assertFalse(original_headline_or_intro_matches(text, TITLE, TERMS))

    def test_footer_related_article_does_not_count_as_publisher_lead(self):
        body = page_text(
            intro="مناقشة طلابية عن ريادة الأعمال.",
            padding=("نص المقال دون العبارة المطلوبة. " * 80)
                    + "footer related news وزارة التخطيط",
        )
        self.assertFalse(original_headline_or_intro_matches(
            body, TITLE, TERMS,
        ))

    def test_absent_original_headline_cannot_match_arbitrary_body(self):
        self.assertFalse(original_headline_or_intro_matches(
            ("وزارة التخطيط خبر قديم " * 50), TITLE, TERMS,
        ))

    def test_browser_adapter_accepts_real_date_and_saved_phrase_in_intro(self):
        page = fake_page(page_text())
        driver = object.__new__(OfficialPageDriver)
        driver.page = page
        receipt = {
            "status": "verified", "id": article_id(URL), "headline": TITLE,
            "sha256": "a" * 64, "published_date_cairo": DAY.isoformat(),
        }
        with tempfile.TemporaryDirectory() as temp:
            with patch("unified_ministry_word._read_original",
                       return_value=receipt) as original:
                output = driver.inspect(
                    URL, keywords=TERMS, target_day=DAY,
                    image=Path(temp) / "original.jpg",
                )
            self.assertEqual(output["status"], "verified")
            original.assert_called_once()
            self.assertEqual(output["published_date_cairo"], DAY.isoformat())

    def test_browser_adapter_rejects_footer_only_and_does_not_capture(self):
        page = fake_page(page_text(
            intro="مناقشة طلابية بلا تطابق.",
            padding=("خبر جامعي قديم لا يرتبط بالوزارة. " * 90)
                    + "footer وزارة التخطيط",
        ))
        driver = object.__new__(OfficialPageDriver)
        driver.page = page
        with tempfile.TemporaryDirectory() as temp:
            with patch("unified_ministry_word._read_original") as original:
                output = driver.inspect(
                    URL, keywords=TERMS, target_day=DAY,
                    image=Path(temp) / "original.jpg",
                )
            self.assertEqual(output["status"], "EXCLUDED_NON_MATCHING_TERM")
            original.assert_not_called()

    def test_original_capture_accepts_lead_only_and_keeps_jpeg_requirement(self):
        with tempfile.TemporaryDirectory() as temp:
            page = fake_page(page_text())
            with patch("official_ministry_source.accept_staged_image",
                       return_value={"ok": True, "sha256": "b" * 64}) as verified:
                out = _read_original(
                    page, URL, TERMS, DAY,
                    Path(temp) / "verified-original.jpg",
                )
            self.assertEqual(out["status"], "verified")
            self.assertEqual(out["published_date_cairo"], DAY.isoformat())
            verified.assert_called_once()
            page.screenshot.assert_called_once()

    def test_original_capture_rejects_body_only_footer_phrase(self):
        with tempfile.TemporaryDirectory() as temp:
            page = fake_page(page_text(
                intro="مناقشة طلابية بلا تطابق.",
                padding=("محتوى المقال دون وزارة محددة. " * 100)
                        + "footer وزير التخطيط",
            ))
            with patch("official_ministry_source.accept_staged_image") as accept:
                out = _read_original(page, URL, TERMS, DAY,
                                     Path(temp) / "original.jpg")
            self.assertEqual(out["status"], "HOLD")
            self.assertEqual(out["reason"], "saved_ministry_keywords_missing")
            accept.assert_not_called()
            page.screenshot.assert_not_called()

    def test_wrong_source_day_never_accepted_even_with_exact_intro(self):
        page = fake_page(page_text())
        driver = object.__new__(OfficialPageDriver)
        driver.page = page
        with tempfile.TemporaryDirectory() as temp:
            with patch("unified_ministry_word._read_original") as original:
                out = driver.inspect(
                    URL, keywords=TERMS, target_day=date(2026, 10, 18),
                    image=Path(temp) / "original.jpg",
                )
            self.assertEqual(out["status"], "OUT_OF_WINDOW")
            original.assert_not_called()

    def test_empty_and_malformed_inputs_rejected(self):
        for body, title in [
            (None, TITLE), (page_text(), None), ("", TITLE), ("a", ""),
        ]:
            self.assertFalse(original_headline_or_intro_matches(
                body, title, TERMS,
            ))


if __name__ == "__main__":
    unittest.main()
