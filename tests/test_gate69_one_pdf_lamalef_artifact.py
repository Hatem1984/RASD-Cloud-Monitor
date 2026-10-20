"""Gate69: correct only independently observed PDF lam-alef glyph-order artifact.

Uses synthetic public-style titles; no real private Word/PDF or owner files.
"""
from types import SimpleNamespace
import unittest

from word_render_audit import (
    _arabic_headline_tokens,
    _verify_headlines_in_independent_pdf_extractions,
)

OFFICIAL = (
    "وزيرا التخطيط والاستثمار في لقاء مفتوح مع 150 من طلاب "
    "الجامعات حول سوق العمل وريادة الأعمال"
)
FIRST = "وزارة التخطيط والتنمية الاقتصادية تناقش خطط الاستثمار القومي"
SECOND = "وزير التخطيط يعرض مؤشرات التعافي والتشغيل والاستثمار"


def document(*headlines):
    return SimpleNamespace(paragraphs=[
        SimpleNamespace(text=f"{i}. {headline}")
        for i, headline in enumerate(headlines, 1)
    ])


class ExactArabicPDFGlyphTranspositionTests(unittest.TestCase):
    def setUp(self):
        self.doc = document(FIRST, SECOND, OFFICIAL)
        self.layout = FIRST + "\n" + SECOND + "\n" + OFFICIAL.replace("طلاب", "طالب")
        # The raw mode corroborates the SAME text-layer artifact, but
        # does not have all other tokens aligned (like actual original CI).
        self.raw = ("وزارة التخطيط وزير التعافي والاستخدام، "
                    + OFFICIAL.replace("طلاب", "طالب"))

    def test_single_reproduced_lamalef_variant_passes_only_when_both_modes_corrob(self):
        expected = _arabic_headline_tokens(OFFICIAL)
        self.assertIn("طلاب", expected)
        self.assertNotIn("طالب", expected)
        self.assertEqual(expected - _arabic_headline_tokens(
            OFFICIAL.replace("طلاب", "طالب"), pdf_extraction=True,
        ), {"طلاب"})
        result = _verify_headlines_in_independent_pdf_extractions(
            self.doc, layout_text=self.layout, raw_text=self.raw,
            expected_articles=3,
        )
        self.assertEqual(
            result, "layout_verified_single_lamalef_glyph_reorder_corrob_raw",
        )

    def test_complete_original_title_still_passes_default_mode(self):
        result = _verify_headlines_in_independent_pdf_extractions(
            self.doc, layout_text="\\n".join((FIRST, SECOND, OFFICIAL)), raw_text="",
            expected_articles=3,
        )
        self.assertEqual(result, "layout")

    def test_other_absent_title_word_is_still_hold(self):
        for missing in ("الجامعات", "العمل", "التعافي"):
            with self.subTest(word=missing):
                bad = self.layout.replace(missing, "غياب", 1)
                with self.assertRaisesRegex(
                    ValueError, "qa_rendered_original_headline_missing",
                ):
                    _verify_headlines_in_independent_pdf_extractions(
                        self.doc, layout_text=bad, raw_text=self.raw,
                        expected_articles=3,
                    )

    def test_one_mode_only_artifact_refused(self):
        with self.assertRaisesRegex(ValueError, "qa_rendered_original_headline_missing"):
            _verify_headlines_in_independent_pdf_extractions(
                self.doc, layout_text=self.layout,
                raw_text="مؤشرات التعافي والتشغيل والاقتصاد",
                expected_articles=3,
            )

    def test_rendered_glyph_variant_must_be_exact_lamalef_reorder(self):
        for wrong in ("طالبين", "طلابنا", "شباب"):
            with self.subTest(wrong=wrong), self.assertRaisesRegex(
                ValueError, "qa_rendered_original_headline_missing",
            ):
                _verify_headlines_in_independent_pdf_extractions(
                    self.doc, layout_text=self.layout.replace("طالب", wrong),
                    raw_text=self.raw, expected_articles=3,
                )

    def test_missing_other_article_heading_does_not_piggyback(self):
        bad = self.layout.replace("التعافي", "الخدمات")
        with self.assertRaisesRegex(ValueError, "qa_rendered_original_headline_missing"):
            _verify_headlines_in_independent_pdf_extractions(
                self.doc, layout_text=bad,
                raw_text=self.raw, expected_articles=3,
            )

    def test_no_multiple_reorders_across_two_different_headings(self):
        dual = document(FIRST, "وزير التخطيط يناقش طلاب الجامعات", OFFICIAL)
        bad_layout = (
            FIRST + "\nوزير التخطيط يناقش طالب الجامعات\n"
            + OFFICIAL.replace("طلاب", "طالب")
        )
        with self.assertRaisesRegex(ValueError, "qa_rendered_original_headline_missing"):
            _verify_headlines_in_independent_pdf_extractions(
                dual, layout_text=bad_layout, raw_text=self.raw,
                expected_articles=3,
            )

    def test_still_refuses_wrong_count(self):
        with self.assertRaisesRegex(ValueError, "qa_original_report_headline_count_mismatch"):
            _verify_headlines_in_independent_pdf_extractions(
                self.doc, layout_text=self.layout, raw_text=self.raw,
                expected_articles=4,
            )


if __name__ == "__main__":
    unittest.main()
