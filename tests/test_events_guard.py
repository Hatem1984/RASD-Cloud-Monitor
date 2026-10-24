import unittest
from event_identity import same_event, distinct_events

def story(headline,key,date="2026-10-24 13:00 EEST"):
    return dict(headline=headline,id=key,published_at_cairo=date)

class TestEventGuard(unittest.TestCase):
    def test_different_numbers(self):
        a=story("ministry planning debt 3 support investment", "a"*24)
        b=story("ministry planning debt 5 support investment", "b"*24)
        self.assertFalse(same_event(a,b))

    def test_arabic_cross_source_equivalent_event(self):
        a=story("\u0648\u0632\u064a\u0631 \u0627\u0644\u062a\u062e\u0637\u064a\u0637 \u064a\u0633\u062a\u0647\u062f\u0641 \u062e\u0641\u0636 \u0627\u0644\u062f\u064a\u0646 \u0627\u0644\u062e\u0627\u0631\u062c\u064a \u0648\u062a\u0639\u0632\u064a\u0632 \u0627\u0644\u0627\u0633\u062a\u062b\u0645\u0627\u0631\u0627\u062a \u0627\u0644\u0623\u062c\u0646\u0628\u064a\u0629 \u062e\u0644\u0627\u0644 \u0627\u0644\u0639\u0627\u0645","a"*24)
        b=story("\u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u062a\u062e\u0637\u064a\u0637 \u062a\u0633\u062a\u0647\u062f\u0641 \u062a\u062e\u0641\u064a\u0636 \u0627\u0644\u062f\u064a\u0646 \u0627\u0644\u062e\u0627\u0631\u062c\u064a \u0648\u062a\u0639\u0632\u064a\u0632 \u0627\u0644\u0627\u0633\u062a\u062b\u0645\u0627\u0631\u0627\u062a \u0627\u0644\u0623\u062c\u0646\u0628\u064a\u0629 \u062e\u0644\u0627\u0644 \u0627\u0644\u0639\u0627\u0645","b"*24)
        self.assertTrue(same_event(a,b))
        self.assertEqual(len(distinct_events([a,b])[0]),1)

    def test_unrelated_arabic_event_remains(self):
        a=story("\u0648\u0632\u064a\u0631 \u0627\u0644\u062a\u062e\u0637\u064a\u0637 \u064a\u0633\u062a\u0647\u062f\u0641 \u062e\u0641\u0636 \u0627\u0644\u062f\u064a\u0646 \u0627\u0644\u062e\u0627\u0631\u062c\u064a \u0648\u062a\u0639\u0632\u064a\u0632 \u0627\u0644\u0627\u0633\u062a\u062b\u0645\u0627\u0631\u0627\u062a \u0627\u0644\u0623\u062c\u0646\u0628\u064a\u0629 \u062e\u0644\u0627\u0644 \u0627\u0644\u0639\u0627\u0645","a"*24)
        b=story("\u0648\u0632\u064a\u0631 \u0627\u0644\u062a\u062e\u0637\u064a\u0637 \u064a\u0639\u0644\u0646 \u062e\u0637\u0629 \u0644\u062f\u0639\u0645 \u0645\u0634\u0631\u0648\u0639\u0627\u062a \u0627\u0644\u0637\u0627\u0642\u0629 \u0627\u0644\u0645\u062a\u062c\u062f\u062f\u0629","b"*24)
        self.assertFalse(same_event(a,b))

    def test_repetition_of_id(self):
        x=story("some headline","a"*24)
        self.assertTrue(same_event(x,x))
        self.assertEqual(len(distinct_events([x,x])[0]),1)

    def test_too_old(self):
        a=story("important ministry budget finance investment","a"*24,
                "2026-10-22 09:00 EEST")
        b=story("important ministry budget finance investment","b"*24)
        self.assertFalse(same_event(a,b))

if __name__ == "__main__":
    unittest.main()
