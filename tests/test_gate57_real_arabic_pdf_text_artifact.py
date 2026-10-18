"""Regression for a reproducible LibreOffice/Poppler Arabic PDF text-layer bug.

This is synthetic QA text, NEVER a publisher news record or output report.
"""
from types import SimpleNamespace
import unittest

from word_render_audit import (
    _arabic_headline_tokens,
    _verify_headlines_in_independent_pdf_extractions,
)


class ArabicDoubleAlefPDFRegressionTests(unittest.TestCase):
    def test_synthetic_actual_libreoffice_layout_artifact_verifies_full_title(self):
        # Independently reproduced with DejaVu Sans, RTL Word -> LibreOffice
        # PDF -> Poppler -layout: the extracted word transposes the first Alef and Lam.
        doc = SimpleNamespace(paragraphs=[SimpleNamespace(
            text="1. وزارة التخطيط والتنمية الاقتصادية تناقش الاستثمار والاقتصاد والابتكار"
        )])
        pdf_text = (
            "وزارة التخطيط والتنمية االقتصادية تناقش "
            "االستثمار واالقتصاد واالبتكار"
        )
        self.assertEqual(
            _verify_headlines_in_independent_pdf_extractions(
                doc, layout_text=pdf_text, raw_text="", expected_articles=1),
            "layout",
        )

    def test_raw_only_mode_can_validate_entire_source_title(self):
        doc = SimpleNamespace(paragraphs=[SimpleNamespace(
            text="1. وزارة التخطيط تستعرض الاستثمار والاقتصاد"
        )])
        self.assertEqual(
            _verify_headlines_in_independent_pdf_extractions(
                doc, layout_text="وزارة التخطيط", raw_text=(
                    "واالقتصاد االستثمار تستعرض التخطيط وزارة"),
                expected_articles=1),
            "raw",
        )

    def test_missing_original_story_subject_cannot_pass(self):
        doc = SimpleNamespace(paragraphs=[SimpleNamespace(
            text="1. وزارة التخطيط تناقش الاستثمار وتطوير الاقتصاد"
        )])
        bad = "وزارة التخطيط تناقش االستثمار االقتصاد"
        with self.assertRaisesRegex(
            ValueError, "qa_rendered_original_headline_missing"
        ):
            _verify_headlines_in_independent_pdf_extractions(
                doc, layout_text=bad, raw_text=bad, expected_articles=1)

    def test_only_one_transposed_initial_alef_is_accepted(self):
        self.assertIn("الاقتصادية", _arabic_headline_tokens(
            "االقتصادية", pdf_extraction=True))
        self.assertNotIn("الاقتصادية", _arabic_headline_tokens(
            "ااالاقتصادية", pdf_extraction=True))

    def test_source_text_is_not_silently_modified(self):
        self.assertIn("االقتصادية", _arabic_headline_tokens(
            "االقتصادية"))
        self.assertNotIn("الاقتصادية", _arabic_headline_tokens(
            "االقتصادية"))

    def test_only_prefix_alef_extraction_case_normalized(self):
        self.assertEqual(
            _arabic_headline_tokens(
                "واالقتصاد باالستثمار", pdf_extraction=True),
            {"والاقتصاد", "بالاستثمار"},
        )
        # Arbitrary mid-word edits and missing original words remain illegal.
        self.assertNotIn("اقتصاد", _arabic_headline_tokens(
            "ااقتصاد", pdf_extraction=True))


if __name__ == "__main__":
    unittest.main()
