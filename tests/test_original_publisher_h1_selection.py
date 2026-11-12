"""No-network tests for selecting the genuine publisher article H1.

The heading is selected only from unchanged publisher DOM content.
A sidebar, missing page title, or ambiguous duplicated H1 must remain HOLD.
"""
import unittest

from capture_public import original_headline_h1_index, headline_visible_in_viewport


class OriginalPublisherH1Selection(unittest.TestCase):
    def test_sidebar_headings_before_real_shorouk_article(self):
        headline = "وزارة التخطيط تعلن تفاصيل خطة التنمية الاقتصادية الجديدة"
        title = headline + " - جريدة الشروق"
        body = (
            "مقتطف من صفحة الناشر " + headline +
            " وتفاصيل موضوع المقالة والبيانات المنشورة."
        )
        headings = [
            "الأخبار الأكثر قراءة اليوم في الصحف",
            "موضوعات أخرى في القسم الاقتصادي",
            "تغطيات من مراسلي الصحيفة اليوم",
            headline,
        ]
        self.assertEqual(original_headline_h1_index(title, body, headings), 3)

    def test_arabic_typography_variants_are_accepted_without_fuzzy_guessing(self):
        heading = "إطلاق المبادرة الوطنية للمشروعات الخضراء الذكية في مصر"
        title = "اطلاق المبادرة الوطنية للمشروعات الخضراء الذكية في مصر - الصحيفة"
        body = "خبر أصلي: " + heading + " وتفاصيل مصدريّة أخرى."
        self.assertEqual(original_headline_h1_index(title, body, [heading]), 0)

    def test_no_title_match_fails_closed(self):
        heading = "وزارة التخطيط تعلن تفاصيل خطة التنمية الاقتصادية الجديدة"
        body = heading + " المزيد من تفاصيل الخبر"
        self.assertIsNone(original_headline_h1_index(
            "أهم أخبار الاقتصاد اليوم", body, [heading]))

    def test_duplicated_headline_is_ambiguous_and_fails_closed(self):
        heading = "وزارة التخطيط تعلن تفاصيل خطة التنمية الاقتصادية الجديدة"
        self.assertIsNone(original_headline_h1_index(
            heading, heading + " معلومات إضافية", [heading, heading]))

    def test_missing_or_invalid_content_fails_closed(self):
        heading = "وزارة التخطيط تعلن تفاصيل خطة التنمية الاقتصادية الجديدة"
        for title, body, headings in (
            (None, heading, [heading]),
            (heading, None, [heading]),
            (heading, heading, None),
            (heading, heading, "not-a-list"),
            (heading, heading, ["وزارة التخطيط", "خبر قصير"]),
            (heading, "نص آخر لا يتضمن الموضوع", [heading]),
        ):
            with self.subTest(title=title, body=body, headings=headings):
                self.assertIsNone(original_headline_h1_index(title, body, headings))

    def test_original_frame_geometry_guard_still_rejects_out_of_view(self):
        viewport = {"width": 1200, "height": 900}
        self.assertFalse(headline_visible_in_viewport(
            {"x": 60, "y": 700, "width": 720, "height": 44}, viewport))
        self.assertTrue(headline_visible_in_viewport(
            {"x": 60, "y": 120, "width": 720, "height": 44}, viewport))


if __name__ == "__main__":
    unittest.main()
