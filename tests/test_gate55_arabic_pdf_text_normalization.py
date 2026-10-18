"""Gate55: NFKC Arabic PDF glyph normalization WITHOUT weakening source proof.

All fixtures are synthetic. Tests never bypass a genuinely missing headline,
original publisher screenshot or Word SHA acceptance.
"""
from types import SimpleNamespace
import unittest

from word_render_audit import (
    _arabic_headline_tokens,
    _verify_original_headlines_in_pdf,
)


class PrivateArabicPDFPresentationTests(unittest.TestCase):
    def test_presentation_forms_lamalef_match_true_arabic_spelling(self):
        standard = "وزارة التخطيط والتنمية الاقتصادية"
        pdf_glyphs = "ﻭﺯﺍﺭﺓ ﺍﻟﺘﺨﻄﻴﻂ ﻭﺍﻟﺘﻨﻤﻴﺔ ﺍﻻﻗﺘﺼﺎﺩﻳﺔ"
        self.assertEqual(
            _arabic_headline_tokens(standard),
            _arabic_headline_tokens(pdf_glyphs),
        )

    def test_diacritics_tatweel_and_common_alef_variants_only_typography(self):
        basic = "وزارة التخطيط الاقتصادية"
        shaped = "وِزارة التّخـطيط الإقتصادية"
        self.assertEqual(
            _arabic_headline_tokens(basic),
            _arabic_headline_tokens(shaped),
        )

    def test_original_headline_visible_as_presentation_forms_is_accepted(self):
        doc = SimpleNamespace(paragraphs=[
            SimpleNamespace(text="1. وزارة التخطيط والتنمية الاقتصادية"),
        ])
        rendered = "ﻭﺯﺍﺭﺓ ﺍﻟﺘﺨﻄﻴﻂ ﻭﺍﻟﺘﻨﻤﻴﺔ ﺍﻻﻗﺘﺼﺎﺩﻳﺔ"
        _verify_original_headlines_in_pdf(doc, rendered, 1)

    def test_missing_original_headline_remains_hold_even_with_normalization(self):
        doc = SimpleNamespace(paragraphs=[
            SimpleNamespace(text="1. وزارة التخطيط تستعرض المؤشرات الاقتصادية"),
        ])
        pdf_wrong = "وزارة التخطيط تنشر نتائج مختلفة"
        with self.assertRaisesRegex(
            ValueError, "qa_rendered_original_headline_missing"
        ):
            _verify_original_headlines_in_pdf(doc, pdf_wrong, 1)

    def test_no_arabic_text_layer_cannot_be_accepted(self):
        doc = SimpleNamespace(paragraphs=[
            SimpleNamespace(text="1. وزارة التخطيط الاقتصادية"),
        ])
        with self.assertRaisesRegex(
            ValueError, "qa_rendered_arabic_text_layer_missing"
        ):
            _verify_original_headlines_in_pdf(doc, "No Arabic glyphs", 1)

    def test_no_original_article_heading_cannot_pass_by_unrelated_text(self):
        doc = SimpleNamespace(paragraphs=[
            SimpleNamespace(text="ملف خال من عنوان الخبر"),
        ])
        with self.assertRaisesRegex(
            ValueError, "qa_original_report_headline_count_mismatch"
        ):
            _verify_original_headlines_in_pdf(
                doc, "وزارة التخطيط الاقتصادية تنشر أخبارا", 1)


if __name__ == "__main__":
    unittest.main()
