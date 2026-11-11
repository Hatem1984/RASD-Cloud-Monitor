"""Publisher-page H1 selection regressions; no browser/network."""
import unittest
from capture_public import original_headline_h1_index
TITLE="وزير التخطيط: 26 مليار دولار حجم محفظة التعاون المشترك بين مصر والبنك الإسلامي للتنمية - الشروق"
H1=["الأكثر قراءة","قد يعجبك أيضا","شارك برأيك",
    "وزير التخطيط: 26 مليار دولار حجم محفظة التعاون المشترك بين مصر والبنك الإسلامي للتنمية"]
BODY="نشرة الأخبار ومقال اليوم " + H1[3] + " وشرح الخبر من المصدر الأصلي"
class OwnerHeadlines(unittest.TestCase):
    def test_shorouk_fourth_heading_selected_not_sidebar(self):
        self.assertEqual(original_headline_h1_index(TITLE,BODY,H1),3)
    def test_unrelated_headline_cannot_be_selected(self):
        self.assertIsNone(original_headline_h1_index("عنوان آخر",BODY,H1))
    def test_no_original_text_in_body_is_hold(self):
        self.assertIsNone(original_headline_h1_index(TITLE,"الأكثر قراءة ومقالات أخرى",H1))
    def test_ambiguous_two_matching_article_headings_is_hold(self):
        self.assertIsNone(original_headline_h1_index(TITLE,BODY,H1+[H1[3]]))
    def test_short_lead_with_topic_name_is_not_enough(self):
        self.assertIsNone(original_headline_h1_index("وزير التخطيط","وزير التخطيط",["وزير التخطيط"]))
if __name__=="__main__":unittest.main()
