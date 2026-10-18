"""Stage 2 Gate56: never pass Arabic headline on partial/combined PDF extraction."""
from types import SimpleNamespace
import unittest
from word_render_audit import _verify_headlines_in_independent_pdf_extractions


class ArabicTitleIndependentPDFModesTests(unittest.TestCase):
    def setUp(self):
        self.doc = SimpleNamespace(paragraphs=[
            SimpleNamespace(text="1. وزارة التخطيط تستعرض مؤشرات الاقتصاد"),
        ])
        self.correct = "وزارة التخطيط تستعرض مؤشرات الاقتصاد الوطني"

    def test_layout_mode_is_preferred_when_complete_original_title_visible(self):
        actual=_verify_headlines_in_independent_pdf_extractions(
            self.doc, layout_text=self.correct, raw_text="",
            expected_articles=1)
        self.assertEqual(actual, "layout")

    def test_raw_mode_verifies_original_title_when_layout_splits_words(self):
        actual=_verify_headlines_in_independent_pdf_extractions(
            self.doc, layout_text="وزارة التخطيط نص متفرق",
            raw_text=self.correct, expected_articles=1)
        self.assertEqual(actual, "raw")

    def test_two_wrong_modes_cannot_be_combined_to_fake_original_title(self):
        for raw in (" ", "وزارة التخطيط خبر آخر"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    _verify_headlines_in_independent_pdf_extractions(
                        self.doc, layout_text="وزارة التخطيط نص مختلف",
                        raw_text=raw, expected_articles=1)

    def test_two_matching_publisher_title_words_cannot_replace_full_headline(self):
        # "وزارة" and "التخطيط" cannot substitute for the entire
        # original headline. All title tokens must survive ONE extraction.
        truncated = "وزارة التخطيط نص مختلف تمامًا"
        with self.assertRaisesRegex(
                ValueError, "qa_rendered_original_headline_missing"):
            _verify_headlines_in_independent_pdf_extractions(
                self.doc, layout_text=truncated, raw_text=truncated,
                expected_articles=1)

    def test_split_headline_across_layout_and_raw_is_rejected(self):
        # Neither extraction alone displays all essential original words.
        with self.assertRaisesRegex(
                ValueError, "qa_rendered_original_headline_missing"):
            _verify_headlines_in_independent_pdf_extractions(
                self.doc, layout_text="وزارة التخطيط تستعرض",
                raw_text="مؤشرات الاقتصاد الوطني والتقارير",
                expected_articles=1)

    def test_missing_article_heading_rejected_even_if_text_layer_has_arabic(self):
        doc=SimpleNamespace(paragraphs=[
            SimpleNamespace(text="مستند من دون عنوان خبر معتمد"),
        ])
        with self.assertRaisesRegex(
                ValueError, "qa_original_report_headline_count_mismatch"):
            _verify_headlines_in_independent_pdf_extractions(
                doc, layout_text=self.correct, raw_text=self.correct,
                expected_articles=1)

    def test_wrong_article_count_rejected(self):
        with self.assertRaisesRegex(
                ValueError, "qa_original_report_headline_count_mismatch"):
            _verify_headlines_in_independent_pdf_extractions(
                self.doc, layout_text=self.correct,
                raw_text=self.correct, expected_articles=2)


if __name__=="__main__":
    unittest.main()
