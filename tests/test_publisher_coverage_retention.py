"""Owner web-reference contract: independent publisher clippings stay separate.

Never conflate event count with outlet-coverage count. Exact same publisher
and article still deduplicate, including private previously delivered items.
"""
import unittest

from event_identity import distinct_publisher_coverages, same_event


HEADLINE = (
    "وزارة التخطيط تستهدف تخفيض الدين الخارجي وتعزيز الاستثمارات "
    "الأجنبية خلال العام"
)


def coverage(publisher, article_id, title=HEADLINE):
    return {
        "id": article_id,
        "source": publisher,
        "headline": title,
        "published_at_cairo": "2026-11-17 10:30 EET",
        "url": "https://original.example/" + article_id,
    }


class PublisherClippingEvidenceTests(unittest.TestCase):
    def test_second_publisher_not_removed_as_same_news_event(self):
        a = coverage("مصدر صحفي أول", "a" * 24)
        b = coverage("مصدر صحفي ثان", "b" * 24)
        self.assertTrue(same_event(a, b))
        retained, suppressed = distinct_publisher_coverages([a, b])
        self.assertEqual(retained, [a, b])
        self.assertEqual(suppressed, [])

    def test_same_publisher_nearly_same_story_deduplicates(self):
        a = coverage("صحيفة معتمدة", "a" * 24)
        b = coverage("صحيفة معتمدة", "b" * 24)
        self.assertTrue(same_event(a, b))
        retained, suppressed = distinct_publisher_coverages([a, b])
        self.assertEqual(retained, [a])
        self.assertEqual(suppressed, [b])

    def test_different_one_digit_government_figures_never_merge(self):
        a = coverage("صحيفة أ", "a" * 24,
                     "وزارة التخطيط تستهدف تنفيذ 3 مشروعات تنموية جديدة")
        b = coverage("صحيفة أ", "b" * 24,
                     "وزارة التخطيط تستهدف تنفيذ 5 مشروعات تنموية جديدة")
        self.assertFalse(same_event(a, b))
        self.assertEqual(len(distinct_publisher_coverages([a, b])[0]),2)

    def test_arabic_single_digits_remain_distinct(self):
        a = coverage("صحيفة أ", "a"*24,
                     "وزارة التخطيط تناقش ٣ مشروعات تطوير جديدة")
        b = coverage("صحيفة أ", "b"*24,
                     "وزارة التخطيط تناقش ٥ مشروعات تطوير جديدة")
        self.assertFalse(same_event(a, b))

    def test_same_original_url_id_is_never_resent(self):
        a = coverage("صحيفة معتمدة", "a" * 24)
        duplicate = coverage("مصدر آخر - بيانات متناقضة", "a" * 24)
        retained, suppressed = distinct_publisher_coverages([duplicate], [a])
        self.assertEqual(retained, [])
        self.assertEqual(suppressed, [duplicate])

    def test_older_sent_coverage_does_not_hide_different_publisher(self):
        already_sent = coverage("صحيفة أ", "a" * 24)
        new_story = coverage("صحيفة ب", "b" * 24)
        retained, suppressed = distinct_publisher_coverages(
            [new_story], history=[already_sent])
        self.assertEqual(retained, [new_story])
        self.assertEqual(suppressed, [])

    def test_missing_publisher_falls_back_to_conservative_event_dedup(self):
        first = coverage(None, "a" * 24)
        second = coverage("صحيفة", "b" * 24)
        retained, suppressed = distinct_publisher_coverages([first, second])
        self.assertEqual(retained, [first])
        self.assertEqual(suppressed, [second])

    def test_different_events_from_same_publisher_retained(self):
        first = coverage("صحيفة", "a" * 24)
        second = coverage("صحيفة", "b" * 24,
                          "وزارة التخطيط تعلن مؤتمر الطاقة المتجددة")
        kept, rejected = distinct_publisher_coverages([first, second])
        self.assertEqual(kept, [first, second])
        self.assertEqual(rejected, [])


if __name__ == "__main__":
    unittest.main()
