import unittest
from event_identity import same_event, distinct_events

def story(headline,key,date="2026-10-24 13:00 EEST"):
    return dict(headline=headline,id=key,published_at_cairo=date)

class TestEventGuard(unittest.TestCase):
    def test_different_numbers(self):
        a=story("ministry planning debt 3 support investment", "a"*24)
        b=story("ministry planning debt 5 support investment", "b"*24)
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
